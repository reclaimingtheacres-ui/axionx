"""geoop_archive.py — Safe administrative archive for GeoOp staging tables.

PURPOSE
-------
The GeoOp staging tables (geoop_staging_jobs, geoop_staging_notes,
geoop_staging_files) were loaded on 13 March 2026 but the import was never
run.  All rows remain marked 'pending' and are not linked to any AxionX job.
This script provides a controlled way to archive those tables to a separate
SQLite database so they can later be cleared from the live database when
production is ready.

SAFETY MODEL
------------
* Default mode is ARCHIVE-ONLY (dry-run).  Source tables are never touched.
* Pass --confirm-delete to also clear the source tables — only after
  row-count validation succeeds.
* Archiving is transactional: the entire copy is written inside a BEGIN
  TRANSACTION block on the destination; the source is only cleared after
  the destination write is confirmed.
* The archive database is separate from the live database and is never
  auto-created at application startup or deployment.
* This script is NOT imported by app.py and is NOT called by any scheduler.

USAGE
-----
  # Dry run — copies data to archive, leaves source untouched (default):
  python geoop_archive.py

  # Specify a custom archive database path:
  python geoop_archive.py --archive-db /path/to/archive.db

  # Archive AND clear source tables (production use — requires confirmation):
  python geoop_archive.py --confirm-delete

  # Override the live database path:
  DB_PATH=/home/site/data/axion.db python geoop_archive.py

PRODUCTION COMMANDS (to run on Azure after reviewing this output locally)
--------------------------------------------------------------------------
  DB_PATH=/home/site/data/axion.db python geoop_archive.py
      # Review the summary report first — no data is deleted in default mode.

  DB_PATH=/home/site/data/axion.db python geoop_archive.py --confirm-delete
      # Only run this after the archive has been verified and a full database
      # backup has been taken.
"""

import argparse
import datetime
import os
import sqlite3
import sys

TABLES = [
    "geoop_staging_jobs",
    "geoop_staging_notes",
    "geoop_staging_files",
]


def _ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_schema(conn, table_name):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    return row[0] if row else None


def _row_count(conn, table_name):
    return conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]


def _table_exists(conn, table_name):
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone())


def archive(src_db_path, archive_db_path, confirm_delete=False):
    print(f"[{_ts()}] === AxionX GeoOp Staging Archive ===")
    print(f"[{_ts()}] Source DB      : {src_db_path}")
    print(f"[{_ts()}] Archive DB     : {archive_db_path}")
    print(f"[{_ts()}] Confirm delete : {confirm_delete}")
    print()

    if not os.path.exists(src_db_path):
        print(f"[{_ts()}] ERROR: Source database not found: {src_db_path}", file=sys.stderr)
        sys.exit(1)

    src = sqlite3.connect(src_db_path)
    src.row_factory = sqlite3.Row

    present_tables = []
    missing_tables = []
    for t in TABLES:
        if _table_exists(src, t):
            present_tables.append(t)
        else:
            missing_tables.append(t)

    if missing_tables:
        print(f"[{_ts()}] WARNING: The following tables do not exist in source and will be skipped:")
        for t in missing_tables:
            print(f"           - {t}")

    if not present_tables:
        print(f"[{_ts()}] Nothing to archive — no staging tables found.")
        src.close()
        return

    src_counts = {}
    for t in present_tables:
        src_counts[t] = _row_count(src, t)
        print(f"[{_ts()}] Source rows  {t}: {src_counts[t]:,}")

    print()

    dst = sqlite3.connect(archive_db_path)
    dst.execute("PRAGMA journal_mode=WAL")

    print(f"[{_ts()}] Phase 1: Copying schemas and data to archive database…")

    dst.execute("BEGIN")
    try:
        for t in present_tables:
            schema_sql = _get_schema(src, t)
            if not schema_sql:
                print(f"[{_ts()}] ERROR: Could not read schema for {t}", file=sys.stderr)
                dst.execute("ROLLBACK")
                src.close()
                dst.close()
                sys.exit(1)

            if _table_exists(dst, t):
                print(f"[{_ts()}]   {t}: already exists in archive — appending rows")
            else:
                dst.execute(schema_sql)
                print(f"[{_ts()}]   {t}: schema created in archive")

            rows = src.execute(f"SELECT * FROM {t}").fetchall()
            if rows:
                cols = rows[0].keys()
                placeholders = ",".join("?" for _ in cols)
                col_names = ",".join(cols)
                dst.executemany(
                    f"INSERT OR IGNORE INTO {t} ({col_names}) VALUES ({placeholders})",
                    [tuple(r) for r in rows]
                )
            print(f"[{_ts()}]   {t}: {len(rows):,} rows written to archive")

        dst.execute("COMMIT")
        print(f"[{_ts()}] Phase 1 complete — all rows committed to archive.")
    except Exception as exc:
        dst.execute("ROLLBACK")
        src.close()
        dst.close()
        print(f"[{_ts()}] ERROR during archive write: {exc}", file=sys.stderr)
        sys.exit(1)

    print()
    print(f"[{_ts()}] Phase 2: Validating row counts…")
    all_valid = True
    for t in present_tables:
        dst_count = _row_count(dst, t)
        ok = dst_count >= src_counts[t]
        status = "OK" if ok else "MISMATCH"
        print(f"[{_ts()}]   {t}: source={src_counts[t]:,}  archive={dst_count:,}  [{status}]")
        if not ok:
            all_valid = False

    print()
    if not all_valid:
        print(f"[{_ts()}] VALIDATION FAILED — row count mismatch. Source tables are unchanged.")
        print(f"[{_ts()}] Review the archive database and re-run.")
        src.close()
        dst.close()
        sys.exit(1)

    print(f"[{_ts()}] Validation passed.")

    if not confirm_delete:
        print()
        print(f"[{_ts()}] *** DRY-RUN / ARCHIVE-ONLY MODE — source tables are NOT modified. ***")
        print(f"[{_ts()}] Re-run with --confirm-delete to clear source tables.")
    else:
        print()
        print(f"[{_ts()}] Phase 3: Clearing source tables (--confirm-delete supplied)…")
        src.execute("BEGIN")
        try:
            for t in present_tables:
                deleted = src.execute(f"DELETE FROM {t}").rowcount
                print(f"[{_ts()}]   {t}: {deleted:,} rows deleted from source")
            src.execute("COMMIT")
            print(f"[{_ts()}] Source tables cleared successfully.")
        except Exception as exc:
            src.execute("ROLLBACK")
            print(f"[{_ts()}] ERROR clearing source tables: {exc}", file=sys.stderr)
            print(f"[{_ts()}] Source tables have NOT been modified (rolled back).")
            src.close()
            dst.close()
            sys.exit(1)

    src.close()
    dst.close()

    print()
    print(f"[{_ts()}] === Summary Report ===")
    for t in present_tables:
        print(f"  {t}: {src_counts[t]:,} rows archived")
    for t in missing_tables:
        print(f"  {t}: not present in source — skipped")
    print(f"  Archive database : {archive_db_path}")
    if confirm_delete:
        print(f"  Source tables    : CLEARED")
    else:
        print(f"  Source tables    : UNCHANGED (archive-only mode)")
    print(f"[{_ts()}] Done.")


def _insert_test_data(db_path):
    """Insert a small set of representative test rows for local testing."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS geoop_staging_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            geoop_job_id TEXT,
            client_name TEXT,
            import_status TEXT DEFAULT 'pending',
            raw_data TEXT,
            imported_at TEXT
        );
        CREATE TABLE IF NOT EXISTS geoop_staging_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            geoop_note_id TEXT,
            geoop_job_id TEXT,
            note_text TEXT,
            import_status TEXT DEFAULT 'pending',
            imported_at TEXT
        );
        CREATE TABLE IF NOT EXISTS geoop_staging_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            geoop_note_id TEXT,
            filename TEXT,
            import_status TEXT DEFAULT 'pending',
            imported_at TEXT
        );
        INSERT OR IGNORE INTO geoop_staging_jobs (geoop_job_id, client_name, import_status)
            VALUES ('GEO-001', 'Test Client A', 'pending'),
                   ('GEO-002', 'Test Client B', 'pending'),
                   ('GEO-003', 'Test Client C', 'pending');
        INSERT OR IGNORE INTO geoop_staging_notes (geoop_note_id, geoop_job_id, note_text, import_status)
            VALUES ('NOTE-001', 'GEO-001', 'Sample field note text', 'pending'),
                   ('NOTE-002', 'GEO-001', 'Another note', 'pending'),
                   ('NOTE-003', 'GEO-002', 'Client note', 'pending');
        INSERT OR IGNORE INTO geoop_staging_files (geoop_note_id, filename, import_status)
            VALUES ('NOTE-001', 'photo1.jpg', 'pending'),
                   ('NOTE-001', 'photo2.jpg', 'pending'),
                   ('NOTE-003', 'doc.pdf', 'pending');
    """)
    conn.commit()
    conn.close()
    print(f"[{_ts()}] Test data inserted into {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Archive GeoOp staging tables to a separate SQLite database."
    )
    parser.add_argument(
        "--archive-db",
        default=None,
        help="Path for the archive SQLite database (default: geoop_staging_archive_YYYY-MM-DD.db)",
    )
    parser.add_argument(
        "--confirm-delete",
        action="store_true",
        default=False,
        help="After successful validation, delete source table rows. Default is archive-only.",
    )
    parser.add_argument(
        "--seed-test-data",
        action="store_true",
        default=False,
        help="Insert representative test rows into the source DB before archiving. "
             "Use only in development/test environments.",
    )
    args = parser.parse_args()

    src_db = os.environ.get("DB_PATH", "axion.db")
    archive_db = args.archive_db or os.path.join(
        os.path.dirname(os.path.abspath(src_db)) or ".",
        f"geoop_staging_archive_{datetime.datetime.now().strftime('%Y-%m-%d')}.db",
    )

    if args.seed_test_data:
        _insert_test_data(src_db)

    archive(src_db, archive_db, confirm_delete=args.confirm_delete)
