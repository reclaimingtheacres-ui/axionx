"""geoop_archive.py — Safe two-stage archive for GeoOp staging tables.

PURPOSE
-------
The GeoOp staging tables (geoop_staging_jobs, geoop_staging_notes,
geoop_staging_files) were loaded on 13 March 2026 but the import was never
run.  All rows remain marked 'pending' and are not linked to any AxionX job.
This script provides a controlled two-stage process to archive those tables to
a separate SQLite database and, only after explicit re-validation, clear them
from the live database.

SAFETY MODEL
------------
Stage 1 — Archive only (default):
  * Copies all rows to a uniquely-named, timestamped archive database.
  * Validates the archive: PRAGMA integrity_check, exact row-count equality
    per table, and primary-key completeness (every source PK present in
    archive, no extras).
  * Refuses to archive into an existing file to prevent accidental append.
  * Writes a <archive>.verified marker file on success.
  * Source tables are NEVER touched in this stage.

Stage 2 — Source deletion:
  * Requires BOTH --confirm-delete AND --archive-db pointing to a specific
    previously archived file.  Cannot be combined with a new archive run.
  * Checks that the .verified marker exists for the named archive.
  * Re-runs the full validation (integrity + counts + PKs) against the
    current source state.  If the source has changed since archiving,
    validation fails and deletion is aborted.
  * Only after passing all checks are source rows deleted.

Additional constraints:
  * This script is NOT imported by app.py and is NOT called by any scheduler.
  * The archive database is entirely separate from the live database.
  * All writes use explicit transactions; errors trigger ROLLBACK.

USAGE
-----
  # Stage 1 — archive to auto-named timestamped file (no source changes):
  python geoop_archive.py

  # Stage 1 — archive to a specific path:
  python geoop_archive.py --archive-db /path/to/my_archive.db

  # Stage 2 — delete source rows referencing a specific verified archive:
  python geoop_archive.py --confirm-delete --archive-db geoop_staging_archive_2026-07-22_134500.db

PRODUCTION COMMANDS (run on Azure only after local verification)
-----------------------------------------------------------------
  # Stage 1 on Azure:
  DB_PATH=/home/site/data/axion.db python geoop_archive.py

  # Stage 2 on Azure — only after reviewing Stage 1 output and taking a
  # full database backup:
  DB_PATH=/home/site/data/axion.db python geoop_archive.py \\
      --confirm-delete --archive-db /home/site/data/geoop_staging_archive_<timestamp>.db
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


def _get_pk_col(conn, table_name):
    """Return the INTEGER PRIMARY KEY column name for the table, or None."""
    for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall():
        if row[5] == 1:   # pk flag
            return row[1]
    return None


def _missing_pks(src, dst, table_name, pk_col):
    """Return sorted list of source PKs absent from the archive."""
    src_ids = {r[0] for r in src.execute(f"SELECT {pk_col} FROM {table_name}").fetchall()}
    dst_ids = {r[0] for r in dst.execute(f"SELECT {pk_col} FROM {table_name}").fetchall()}
    return sorted(src_ids - dst_ids)


def _extra_pks(src, dst, table_name, pk_col):
    """Return sorted list of archive PKs not present in the source."""
    src_ids = {r[0] for r in src.execute(f"SELECT {pk_col} FROM {table_name}").fetchall()}
    dst_ids = {r[0] for r in dst.execute(f"SELECT {pk_col} FROM {table_name}").fetchall()}
    return sorted(dst_ids - src_ids)


def _integrity_check(conn, label):
    """Run PRAGMA integrity_check on conn.  Returns list of failure messages.

    A healthy database returns exactly one row: 'ok'.
    """
    rows = conn.execute("PRAGMA integrity_check").fetchall()
    if not rows:
        return [f"{label}: integrity_check returned no rows"]
    return [r[0] for r in rows if r[0] != "ok"]


def _validate_archive(src, dst, present_tables, src_counts, label="archive"):
    """Full validation of the archive against source.

    Checks (in order):
      1. PRAGMA integrity_check — all rows must be 'ok'
      2. Exact row count equality per table (not >=)
      3. Primary-key completeness — no source PKs missing; no extra PKs in archive

    Returns (passed: bool, messages: list[str]).
    """
    messages = []
    passed = True

    # 1. Integrity check
    failures = _integrity_check(dst, label)
    if failures:
        passed = False
        detail = "; ".join(failures[:5])
        suffix = f" (and {len(failures)-5} more)" if len(failures) > 5 else ""
        messages.append(f"  INTEGRITY CHECK FAILED: {detail}{suffix}")
    else:
        messages.append(f"  integrity_check: ok")

    for t in present_tables:
        dst_count = _row_count(dst, t)
        src_count = src_counts[t]

        # 2. Exact count equality
        if dst_count != src_count:
            passed = False
            messages.append(
                f"  COUNT MISMATCH  {t}: source={src_count:,}  archive={dst_count:,}"
            )
        else:
            messages.append(
                f"  count ok        {t}: {src_count:,} rows"
            )

        # 3. PK completeness
        pk_col = _get_pk_col(src, t)
        if pk_col:
            missing = _missing_pks(src, dst, t, pk_col)
            extras  = _extra_pks(src, dst, t, pk_col)
            if missing:
                passed = False
                sample = missing[:10]
                suffix = f" (and {len(missing)-10} more)" if len(missing) > 10 else ""
                messages.append(
                    f"  MISSING PKs     {t}.{pk_col}: {sample}{suffix}"
                )
            if extras:
                passed = False
                sample = extras[:10]
                suffix = f" (and {len(extras)-10} more)" if len(extras) > 10 else ""
                messages.append(
                    f"  EXTRA PKs       {t}.{pk_col}: {sample}{suffix}"
                )
            if not missing and not extras:
                messages.append(
                    f"  pk ok           {t}.{pk_col}: all IDs present, no extras"
                )
        else:
            messages.append(f"  pk check skipped {t}: no INTEGER PRIMARY KEY found")

    return passed, messages


def _verified_marker(archive_db_path):
    return archive_db_path + ".verified"


def archive(src_db_path, archive_db_path):
    """Stage 1: copy staging tables to a new archive DB and validate.

    Raises SystemExit on any failure.  Source tables are never modified.
    """
    print(f"[{_ts()}] === AxionX GeoOp Staging Archive — Stage 1: Archive ===")
    print(f"[{_ts()}] Source DB  : {src_db_path}")
    print(f"[{_ts()}] Archive DB : {archive_db_path}")
    print()

    if not os.path.exists(src_db_path):
        print(f"[{_ts()}] ERROR: Source database not found: {src_db_path}", file=sys.stderr)
        sys.exit(1)

    if os.path.exists(archive_db_path):
        print(
            f"[{_ts()}] ERROR: Archive file already exists: {archive_db_path}\n"
            f"[{_ts()}]        Use a new path or delete the existing file first.\n"
            f"[{_ts()}]        (Each archive run must write to a fresh file to prevent\n"
            f"[{_ts()}]         accidental row mixing from prior runs.)",
            file=sys.stderr,
        )
        sys.exit(1)

    src = sqlite3.connect(src_db_path)
    src.row_factory = sqlite3.Row

    present_tables, missing_tables = [], []
    for t in TABLES:
        (present_tables if _table_exists(src, t) else missing_tables).append(t)

    if missing_tables:
        print(f"[{_ts()}] NOTE: Tables not found in source (will be skipped):")
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

    # ── Phase 1: copy ─────────────────────────────────────────────────────────
    print(f"[{_ts()}] Phase 1: Copying schemas and data to archive database…")
    dst = sqlite3.connect(archive_db_path)
    dst.execute("PRAGMA journal_mode=WAL")
    dst.execute("BEGIN")
    try:
        for t in present_tables:
            schema_sql = _get_schema(src, t)
            if not schema_sql:
                print(f"[{_ts()}] ERROR: Could not read schema for {t}", file=sys.stderr)
                dst.execute("ROLLBACK")
                src.close(); dst.close()
                sys.exit(1)

            dst.execute(schema_sql)
            print(f"[{_ts()}]   {t}: schema created")

            rows = src.execute(f"SELECT * FROM {t}").fetchall()
            if rows:
                cols = rows[0].keys()
                placeholders = ",".join("?" for _ in cols)
                col_names = ",".join(cols)
                dst.executemany(
                    f"INSERT INTO {t} ({col_names}) VALUES ({placeholders})",
                    [tuple(r) for r in rows]
                )
            print(f"[{_ts()}]   {t}: {len(rows):,} rows written")

        dst.execute("COMMIT")
        print(f"[{_ts()}] Phase 1 complete.")
    except Exception as exc:
        dst.execute("ROLLBACK")
        src.close(); dst.close()
        try:
            os.remove(archive_db_path)
        except OSError:
            pass
        print(f"[{_ts()}] ERROR during archive write: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Phase 2: validate ─────────────────────────────────────────────────────
    print()
    print(f"[{_ts()}] Phase 2: Validating archive (integrity + counts + PKs)…")
    passed, msgs = _validate_archive(src, dst, present_tables, src_counts)
    for m in msgs:
        print(f"[{_ts()}] {m}")

    src.close(); dst.close()

    if not passed:
        print()
        print(f"[{_ts()}] VALIDATION FAILED — archive database is unreliable.")
        print(f"[{_ts()}] Removing invalid archive: {archive_db_path}")
        try:
            os.remove(archive_db_path)
        except OSError as e:
            print(f"[{_ts()}] WARNING: could not remove archive file: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Write verified marker ─────────────────────────────────────────────────
    marker = _verified_marker(archive_db_path)
    with open(marker, "w") as f:
        f.write(
            f"archive_db: {archive_db_path}\n"
            f"verified_at: {_ts()}\n"
            f"tables: {', '.join(present_tables)}\n"
        )
        for t in present_tables:
            f.write(f"  {t}: {src_counts[t]} rows\n")

    print()
    print(f"[{_ts()}] === Archive complete ===")
    print(f"[{_ts()}] Archive DB      : {archive_db_path}")
    print(f"[{_ts()}] Verified marker : {marker}")
    print(f"[{_ts()}] Source tables   : UNCHANGED")
    print()
    print(f"[{_ts()}] To clear source tables, run:")
    print(f"[{_ts()}]   python geoop_archive.py --confirm-delete --archive-db {archive_db_path}")


def delete_source(src_db_path, archive_db_path):
    """Stage 2: delete source rows, referencing a specific verified archive.

    Requires the .verified marker to exist.
    Re-runs full validation before deleting anything.
    Raises SystemExit on any failure.
    """
    print(f"[{_ts()}] === AxionX GeoOp Staging Archive — Stage 2: Delete Source ===")
    print(f"[{_ts()}] Source DB  : {src_db_path}")
    print(f"[{_ts()}] Archive DB : {archive_db_path}")
    print()

    marker = _verified_marker(archive_db_path)
    if not os.path.exists(marker):
        print(
            f"[{_ts()}] ERROR: Verified marker not found: {marker}\n"
            f"[{_ts()}]        Run Stage 1 first and ensure it completes with 'Archive complete'.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.exists(archive_db_path):
        print(f"[{_ts()}] ERROR: Archive DB not found: {archive_db_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(src_db_path):
        print(f"[{_ts()}] ERROR: Source DB not found: {src_db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[{_ts()}] Verified marker: present")

    src = sqlite3.connect(src_db_path)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(archive_db_path)

    present_tables = [t for t in TABLES if _table_exists(src, t)]
    if not present_tables:
        print(f"[{_ts()}] No staging tables found in source — nothing to delete.")
        src.close(); dst.close()
        return

    src_counts = {t: _row_count(src, t) for t in present_tables}
    for t in present_tables:
        print(f"[{_ts()}] Source rows  {t}: {src_counts[t]:,}")
    print()

    # ── Re-validate before deleting ───────────────────────────────────────────
    print(f"[{_ts()}] Re-validating archive before deletion…")
    passed, msgs = _validate_archive(src, dst, present_tables, src_counts, "archive (re-check)")
    for m in msgs:
        print(f"[{_ts()}] {m}")

    if not passed:
        print()
        print(f"[{_ts()}] VALIDATION FAILED — source tables have NOT been modified.")
        print(f"[{_ts()}] The archive may be stale or the source may have changed since archiving.")
        src.close(); dst.close()
        sys.exit(1)

    # ── Delete source rows ────────────────────────────────────────────────────
    print()
    print(f"[{_ts()}] Phase 3: Clearing source tables…")
    src.execute("BEGIN")
    try:
        for t in present_tables:
            deleted = src.execute(f"DELETE FROM {t}").rowcount
            print(f"[{_ts()}]   {t}: {deleted:,} rows deleted")
        src.execute("COMMIT")
    except Exception as exc:
        src.execute("ROLLBACK")
        src.close(); dst.close()
        print(f"[{_ts()}] ERROR clearing source tables: {exc}", file=sys.stderr)
        print(f"[{_ts()}] Source tables have NOT been modified (rolled back).")
        sys.exit(1)

    src.close(); dst.close()

    print()
    print(f"[{_ts()}] === Stage 2 complete ===")
    for t in present_tables:
        print(f"  {t}: {src_counts[t]:,} rows deleted from source")
    print(f"  Archive preserved : {archive_db_path}")


def _insert_test_data(db_path):
    """Insert representative test rows for local testing only."""
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
        description=(
            "Two-stage safe archive for GeoOp staging tables.\n"
            "Stage 1 (default): archive to a new timestamped DB, validate, write .verified marker.\n"
            "Stage 2: --confirm-delete --archive-db <path> re-validates and deletes source rows."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--archive-db",
        default=None,
        help=(
            "Stage 1: path for the new archive database "
            "(default: auto-named with timestamp in same dir as source DB). "
            "Stage 2: required — path to the specific .verified archive to reference."
        ),
    )
    parser.add_argument(
        "--confirm-delete",
        action="store_true",
        default=False,
        help=(
            "Stage 2: delete source table rows.  REQUIRES --archive-db pointing "
            "to a specific previously validated archive.  Cannot create a new archive "
            "in the same invocation."
        ),
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

    if args.confirm_delete:
        if not args.archive_db:
            print(
                "ERROR: --confirm-delete requires --archive-db pointing to a specific\n"
                "       previously validated archive.  Run without --confirm-delete first.",
                file=sys.stderr,
            )
            sys.exit(1)
        delete_source(src_db, args.archive_db)
    else:
        if args.seed_test_data:
            _insert_test_data(src_db)

        # Default archive path: unique timestamp including time (seconds) so
        # multiple runs on the same day each produce a distinct file.
        archive_db = args.archive_db or os.path.join(
            os.path.dirname(os.path.abspath(src_db)) or ".",
            f"geoop_staging_archive_{datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db",
        )
        archive(src_db, archive_db)
