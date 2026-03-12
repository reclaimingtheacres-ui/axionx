import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import uuid
import zipfile
from datetime import datetime

UPLOAD_FOLDER = "uploads"
GEOOP_IMPORT_DIR = os.path.join(UPLOAD_FOLDER, "geoop_import")
os.makedirs(GEOOP_IMPORT_DIR, exist_ok=True)


_DB_PATH = os.path.abspath(os.getenv("DB_PATH", "axion.db"))


def _db(db_path=None):
    conn = sqlite3.connect(db_path or _DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def _now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def ensure_staging_tables(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS geoop_staging_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        geoop_job_id TEXT NOT NULL,
        geoop_account_id TEXT,
        reference_no TEXT,
        job_title TEXT,
        raw_description TEXT,
        status_label TEXT,
        address TEXT,
        suburb TEXT,
        city TEXT,
        postcode TEXT,
        company TEXT,
        firstname TEXT,
        lastname TEXT,
        email TEXT,
        phone TEXT,
        mobile TEXT,
        created_by TEXT,
        modified_by TEXT,
        date_created TEXT,
        date_modified TEXT,
        file_locations TEXT,

        parsed_client_name TEXT,
        parsed_account_number TEXT,
        parsed_regulation_type TEXT,
        parsed_amount_type TEXT,
        parsed_amount_cents INTEGER,
        parsed_costs_cents INTEGER,
        parsed_nmpd_amount_cents INTEGER,
        parsed_nmpd_date TEXT,
        parsed_security_description TEXT,
        parsed_security_colour TEXT,
        parsed_security_year TEXT,
        parsed_security_make TEXT,
        parsed_security_model TEXT,
        parsed_reg TEXT,
        parsed_vin TEXT,
        parsed_deliver_to TEXT,
        parsed_notes TEXT,

        import_status TEXT NOT NULL DEFAULT 'pending',
        axion_job_id INTEGER,
        axion_customer_id INTEGER,
        axion_client_id INTEGER,
        error_message TEXT,
        imported_at TEXT,
        created_at TEXT NOT NULL,

        UNIQUE(geoop_job_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS geoop_staging_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        geoop_job_id TEXT NOT NULL,
        geoop_note_id TEXT NOT NULL,
        geoop_account_id TEXT,
        job_reference TEXT,
        note_description TEXT,
        files_location TEXT,
        file_name TEXT,
        file_date TEXT,

        import_status TEXT NOT NULL DEFAULT 'pending',
        axion_job_id INTEGER,
        axion_note_id INTEGER,
        error_message TEXT,
        imported_at TEXT,
        created_at TEXT NOT NULL,

        UNIQUE(geoop_note_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS geoop_staging_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL,
        geoop_job_id TEXT,
        geoop_note_id TEXT,
        files_location TEXT,
        file_name TEXT,
        original_path TEXT,
        file_hash TEXT,
        file_size INTEGER,
        mime_type TEXT,
        found_on_disk INTEGER NOT NULL DEFAULT 0,
        disk_path TEXT,

        import_status TEXT NOT NULL DEFAULT 'pending',
        axion_doc_id INTEGER,
        stored_filename TEXT,
        deduplicated INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        imported_at TEXT,
        created_at TEXT NOT NULL,

        UNIQUE(files_location, file_name)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS geoop_import_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'running',
        jobs_csv_path TEXT,
        notes_csv_path TEXT,
        attachment_dirs TEXT,
        total_jobs INTEGER DEFAULT 0,
        total_notes INTEGER DEFAULT 0,
        total_files INTEGER DEFAULT 0,
        jobs_imported INTEGER DEFAULT 0,
        notes_imported INTEGER DEFAULT 0,
        files_imported INTEGER DEFAULT 0,
        jobs_skipped INTEGER DEFAULT 0,
        notes_skipped INTEGER DEFAULT 0,
        files_skipped INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0,
        diagnostics_json TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        run_by_user_id INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS geoop_unmatched_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        zip_name TEXT,
        entry_path TEXT NOT NULL,
        filename TEXT,
        geoop_job_id TEXT,
        geoop_note_id TEXT,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    if close:
        conn.close()


def _parse_money(s):
    if not s:
        return 0
    s = s.replace(",", "").replace("$", "").replace(" ", "").strip()
    try:
        return int(float(s) * 100)
    except (ValueError, TypeError):
        return 0


def parse_description(desc):
    if not desc:
        return {}

    result = {}
    original = desc.strip()

    prefixes = []
    prefix_patterns = [
        r'\*+[^*]+\*+',
        r'REPOSSESSION AUTHORITY[^.]+\.',
    ]
    clean = original
    for pp in prefix_patterns:
        m = re.match(pp, clean, re.IGNORECASE)
        if m:
            prefixes.append(m.group().strip("* "))
            clean = clean[m.end():].strip()

    if prefixes:
        result["parsed_notes"] = " | ".join(prefixes)

    vin_match = re.search(r'VIN[:\s]*([A-HJ-NPR-Z0-9]{17})', clean, re.IGNORECASE)
    if vin_match:
        result["parsed_vin"] = vin_match.group(1).upper()

    reg_match = re.search(r'REG[:\s]*([A-Z0-9]{2,10}(?:\s*\([^)]*\))?)', clean, re.IGNORECASE)
    if reg_match:
        raw_reg = reg_match.group(1).strip()
        reg_clean = re.sub(r'\s*\([^)]*\)$', '', raw_reg).strip().upper()
        result["parsed_reg"] = reg_clean

    deliver_match = re.search(r'Deliver\s+to[:\s]*(.+?)(?:\.\s*$|$)', clean, re.IGNORECASE)
    if deliver_match:
        result["parsed_deliver_to"] = deliver_match.group(1).strip().rstrip(".")

    reg_match_type = re.search(r'\b(Regulated|Unregulated)\b', clean, re.IGNORECASE)
    if reg_match_type:
        result["parsed_regulation_type"] = reg_match_type.group(1).capitalize()

    payout_match = re.search(r'Payout\s+\$?([\d,]+\.?\d*)', clean, re.IGNORECASE)
    arrears_match = re.search(r'Arrears[:\s]*\$?\s*([\d,]+\.?\d*)', clean, re.IGNORECASE)
    balance_match = re.search(r'Balance\s+\$?([\d,]+\.?\d*)', clean, re.IGNORECASE)
    ctd_match = re.search(r'CTD\s+\$?([\d,]+\.?\d*)', clean, re.IGNORECASE)
    full_debt_match = re.search(r'Full\s+debt[:\s]*\$?([\d,]+\.?\d*)', clean, re.IGNORECASE)
    pof_match = re.search(r'POF[:\s]*\$?\s*([\d,]+\.?\d*)', clean, re.IGNORECASE)

    if payout_match:
        result["parsed_amount_type"] = "Payout"
        result["parsed_amount_cents"] = _parse_money(payout_match.group(1))
    elif arrears_match:
        result["parsed_amount_type"] = "Arrears"
        result["parsed_amount_cents"] = _parse_money(arrears_match.group(1))
    elif balance_match:
        result["parsed_amount_type"] = "Balance"
        result["parsed_amount_cents"] = _parse_money(balance_match.group(1))
    elif ctd_match:
        result["parsed_amount_type"] = "CTD"
        result["parsed_amount_cents"] = _parse_money(ctd_match.group(1))
    elif full_debt_match:
        result["parsed_amount_type"] = "Full Debt"
        result["parsed_amount_cents"] = _parse_money(full_debt_match.group(1))
    elif pof_match:
        result["parsed_amount_type"] = "POF"
        result["parsed_amount_cents"] = _parse_money(pof_match.group(1))

    costs_match = re.search(r'[Cc]osts?\s+(?:of\s+)?\$?\s*([\d,]+\.?\d*)', clean)
    if costs_match:
        result["parsed_costs_cents"] = _parse_money(costs_match.group(1))

    nmpd_match = re.search(
        r'N[MW]PD\s+\$?\s*([\d,]+\.?\d*)\s+(?:on\s+(?:the\s+)?)?(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
        clean, re.IGNORECASE
    )
    if not nmpd_match:
        nmpd_match = re.search(
            r'NPD[:\s]*\$?\s*([\d,]+\.?\d*)\s+(?:on\s+)?(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
            clean, re.IGNORECASE
        )
    if not nmpd_match:
        nmpd_match = re.search(
            r'N[FW]PD\s+\$?\s*([\d,]+\.?\d*)\s+(?:on\s+)?(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
            clean, re.IGNORECASE
        )
    if nmpd_match:
        result["parsed_nmpd_amount_cents"] = _parse_money(nmpd_match.group(1))
        result["parsed_nmpd_date"] = nmpd_match.group(2)

    sec_match = re.search(r'Security[:\s]*(.+?)(?:\s+REG[:\s]|\s+VIN[:\s]|Deliver\s+to|$)', clean, re.IGNORECASE)
    if sec_match:
        sec_desc = sec_match.group(1).strip().rstrip(",.")
        result["parsed_security_description"] = sec_desc

        colour_match = re.match(r'^(Black|White|Grey|Gray|Silver|Red|Blue|Green|Gold|Brown|Beige|Maroon|Yellow|Orange|Purple)\s+', sec_desc, re.IGNORECASE)
        if colour_match:
            result["parsed_security_colour"] = colour_match.group(1).capitalize()
            sec_desc = sec_desc[colour_match.end():]

        year_match = re.match(r'^(\d{4})\s+', sec_desc)
        if year_match:
            result["parsed_security_year"] = year_match.group(1)
            sec_desc = sec_desc[year_match.end():]

        words = sec_desc.split()
        if len(words) >= 2:
            result["parsed_security_make"] = words[0]
            result["parsed_security_model"] = " ".join(words[1:])
        elif len(words) == 1:
            result["parsed_security_make"] = words[0]

    client_patterns = [
        r'^(.+?)\s*-\s*(\w[\w\-/]+)',
        r'^(.+?)\s+account\s+(\w[\w\-/]+)',
    ]
    for cp in client_patterns:
        cm = re.match(cp, clean, re.IGNORECASE)
        if cm:
            client_name = cm.group(1).strip().rstrip(" -")
            account_num = cm.group(2).strip()
            if len(client_name) > 2 and len(client_name) < 100:
                if not any(kw in client_name.lower() for kw in ["security", "arrears", "regulated"]):
                    result["parsed_client_name"] = client_name
                    result["parsed_account_number"] = account_num
                    break

    dual_account = re.search(
        r'(\w+)\s+account\s+([\w\-/]+)\s*/\s*(\w.+?)\s+account\s+([\w\-/]+)',
        clean, re.IGNORECASE
    )
    if dual_account:
        result["parsed_client_name"] = dual_account.group(3).strip()
        result["parsed_account_number"] = dual_account.group(4).strip()

    return result


def stage_jobs_csv(csv_path, conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ensure_staging_tables(conn)
    ts = _now()
    inserted = 0
    skipped = 0
    errors = 0
    error_details = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            geoop_id = (row.get("Job ID") or "").strip()
            if not geoop_id:
                errors += 1
                continue

            desc = row.get("Description", "")
            parsed = parse_description(desc)

            batch.append((
                geoop_id,
                row.get("Account ID", ""),
                row.get("Reference no.", ""),
                row.get("Job Title", ""),
                desc,
                row.get("Status Label", ""),
                row.get("Address", ""),
                row.get("Suburb", ""),
                row.get("City", ""),
                row.get("Postcode", ""),
                row.get("Company", ""),
                row.get("Firstname", ""),
                row.get("Lastname", ""),
                row.get("Email", ""),
                row.get("Phone", ""),
                row.get("Mobile", ""),
                row.get("Created By", ""),
                row.get("Modified By", ""),
                row.get("Date Created", ""),
                row.get("Date Modified", ""),
                row.get("File Locations", ""),
                parsed.get("parsed_client_name", ""),
                parsed.get("parsed_account_number", ""),
                parsed.get("parsed_regulation_type", ""),
                parsed.get("parsed_amount_type", ""),
                parsed.get("parsed_amount_cents", 0),
                parsed.get("parsed_costs_cents", 0),
                parsed.get("parsed_nmpd_amount_cents", 0),
                parsed.get("parsed_nmpd_date", ""),
                parsed.get("parsed_security_description", ""),
                parsed.get("parsed_security_colour", ""),
                parsed.get("parsed_security_year", ""),
                parsed.get("parsed_security_make", ""),
                parsed.get("parsed_security_model", ""),
                parsed.get("parsed_reg", ""),
                parsed.get("parsed_vin", ""),
                parsed.get("parsed_deliver_to", ""),
                parsed.get("parsed_notes", ""),
                ts,
            ))

            if len(batch) >= 500:
                ins, skip = _insert_job_batch(conn, batch)
                inserted += ins
                skipped += skip
                batch = []

        if batch:
            ins, skip = _insert_job_batch(conn, batch)
            inserted += ins
            skipped += skip

    if close:
        conn.close()
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def _insert_job_batch(conn, batch):
    inserted = 0
    skipped = 0
    for row in batch:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO geoop_staging_jobs (
                    geoop_job_id, geoop_account_id, reference_no, job_title, raw_description,
                    status_label, address, suburb, city, postcode,
                    company, firstname, lastname, email, phone, mobile,
                    created_by, modified_by, date_created, date_modified, file_locations,
                    parsed_client_name, parsed_account_number, parsed_regulation_type,
                    parsed_amount_type, parsed_amount_cents, parsed_costs_cents,
                    parsed_nmpd_amount_cents, parsed_nmpd_date,
                    parsed_security_description, parsed_security_colour,
                    parsed_security_year, parsed_security_make, parsed_security_model,
                    parsed_reg, parsed_vin, parsed_deliver_to, parsed_notes,
                    created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, row)
            if conn.total_changes:
                inserted += 1
            else:
                skipped += 1
        except sqlite3.IntegrityError:
            skipped += 1
    conn.commit()
    return inserted, skipped


def _ensure_rejects_table(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS geoop_notes_rejects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        csv_row_number INTEGER,
        geoop_job_id TEXT,
        geoop_note_id TEXT,
        reject_reason TEXT NOT NULL,
        raw_note_description TEXT,
        raw_fields_json TEXT,
        created_at TEXT NOT NULL
    )
    """)
    conn.commit()


def stage_notes_csv(csv_path, conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ensure_staging_tables(conn)
    _ensure_rejects_table(conn)
    conn.execute("DELETE FROM geoop_notes_rejects")
    conn.commit()
    ts = _now()

    inserted = 0
    skip_missing_job_id = 0
    skip_missing_note_id = 0
    skip_duplicate_note_id = 0
    skip_csv_error = 0
    total_read = 0

    seen_note_ids = set()

    existing = conn.execute("SELECT geoop_note_id FROM geoop_staging_notes").fetchall()
    for r in existing:
        seen_note_ids.add(r[0] if isinstance(r, tuple) else r["geoop_note_id"])

    reject_batch = []

    def _flush_rejects():
        nonlocal reject_batch
        if reject_batch:
            conn.executemany("""
                INSERT INTO geoop_notes_rejects
                    (csv_row_number, geoop_job_id, geoop_note_id, reject_reason, raw_note_description, raw_fields_json, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, reject_batch)
            conn.commit()
            reject_batch = []

    def _reject(row_num, job_id, note_id, reason, desc, row_dict):
        raw_json = ""
        try:
            import json as _j
            raw_json = _j.dumps({k: (v[:200] if isinstance(v, str) else v) for k, v in (row_dict or {}).items()})
        except Exception:
            pass
        reject_batch.append((row_num, job_id or "", note_id or "", reason, (desc or "")[:500], raw_json, ts))
        if len(reject_batch) >= 500:
            _flush_rejects()

    insert_batch = []

    def _flush_inserts():
        nonlocal insert_batch, inserted, skip_duplicate_note_id
        for row in insert_batch:
            cur = conn.execute("""
                INSERT OR IGNORE INTO geoop_staging_notes (
                    geoop_job_id, geoop_note_id, geoop_account_id, job_reference,
                    note_description, files_location, file_name, file_date, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
            """, row)
            if cur.rowcount == 1:
                inserted += 1
            else:
                skip_duplicate_note_id += 1
                _reject(0, row[0], row[1], "duplicate_note_id_db", row[4], None)
        conn.commit()
        insert_batch = []

    try:
        with open(csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_read += 1
                row_num = total_read + 1

                geoop_job_id = (row.get("job_id") or "").strip()
                geoop_note_id = (row.get("note_id") or "").strip()
                note_desc = row.get("note_description", "")

                if not geoop_job_id:
                    skip_missing_job_id += 1
                    _reject(row_num, geoop_job_id, geoop_note_id, "missing_job_id", note_desc, row)
                    continue
                if not geoop_note_id:
                    skip_missing_note_id += 1
                    _reject(row_num, geoop_job_id, geoop_note_id, "missing_note_id", note_desc, row)
                    continue

                if geoop_note_id in seen_note_ids:
                    skip_duplicate_note_id += 1
                    _reject(row_num, geoop_job_id, geoop_note_id, "duplicate_note_id", note_desc, row)
                    continue
                seen_note_ids.add(geoop_note_id)

                insert_batch.append((
                    geoop_job_id,
                    geoop_note_id,
                    row.get("account_id", ""),
                    row.get("job_reference", ""),
                    note_desc,
                    row.get("files_location", ""),
                    row.get("file_name", ""),
                    row.get("file_date", ""),
                    ts,
                ))

                if len(insert_batch) >= 2000:
                    _flush_inserts()

        if insert_batch:
            _flush_inserts()
        _flush_rejects()
    except Exception as e:
        skip_csv_error += 1
        try:
            _flush_rejects()
        except Exception:
            pass
        raise
    finally:
        if close:
            conn.close()

    return {
        "total_read": total_read,
        "inserted": inserted,
        "skipped": skip_missing_job_id + skip_missing_note_id + skip_duplicate_note_id,
        "errors": skip_csv_error,
        "breakdown": {
            "missing_job_id": skip_missing_job_id,
            "missing_note_id": skip_missing_note_id,
            "duplicate_note_id": skip_duplicate_note_id,
            "csv_parse_error": skip_csv_error,
        }
    }


def scan_attachment_dirs(dirs, conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ensure_staging_tables(conn)
    ts = _now()
    found = 0
    skipped = 0

    for base_dir in dirs:
        if not os.path.isdir(base_dir):
            continue
        for root, _dirs, files in os.walk(base_dir):
            for fname in files:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, base_dir)

                parts = rel_path.replace("\\", "/").split("/")
                files_loc = "/".join(parts[:-1]) + "/" if len(parts) > 1 else ""

                geoop_job_id = ""
                geoop_note_id = ""
                if len(parts) >= 4:
                    geoop_job_id = parts[0]
                    geoop_note_id = parts[1]
                elif len(parts) == 3:
                    geoop_job_id = parts[0]
                    geoop_note_id = parts[1]
                elif len(parts) == 2:
                    geoop_job_id = parts[0]

                try:
                    fsize = os.path.getsize(full_path)
                    with open(full_path, 'rb') as fh:
                        fhash = hashlib.md5(fh.read()).hexdigest()
                except OSError:
                    continue

                mime = mimetypes.guess_type(fname)[0] or "application/octet-stream"

                try:
                    cur = conn.execute("""
                        UPDATE geoop_staging_files
                        SET found_on_disk=1, disk_path=?, file_hash=?, file_size=?, mime_type=?
                        WHERE files_location=? AND file_name=? AND source_type IN ('note_csv','job_csv')
                    """, (full_path, fhash, fsize, mime, files_loc, fname))
                    if cur.rowcount > 0:
                        found += 1
                    else:
                        conn.execute("""
                            INSERT OR IGNORE INTO geoop_staging_files (
                                source_type, geoop_job_id, geoop_note_id, files_location, file_name,
                                original_path, file_hash, file_size, mime_type, found_on_disk, disk_path, created_at
                            ) VALUES (?,?,?,?,?,?,?,?,?,1,?,?)
                        """, (
                            "disk_scan", geoop_job_id, geoop_note_id, files_loc, fname,
                            full_path, fhash, fsize, mime, full_path, ts
                        ))
                        found += 1
                except sqlite3.IntegrityError:
                    skipped += 1

    conn.commit()
    if close:
        conn.close()
    return {"found": found, "skipped": skipped}


def build_file_manifest_from_csv(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ts = _now()
    inserted = 0
    skipped = 0

    job_files = conn.execute("""
        SELECT geoop_job_id, file_locations FROM geoop_staging_jobs
        WHERE file_locations IS NOT NULL AND file_locations != ''
    """).fetchall()
    for row in job_files:
        locs = [l.strip() for l in row["file_locations"].split(",") if l.strip()]
        for loc in locs:
            loc = loc.rstrip("/") + "/"
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO geoop_staging_files (
                        source_type, geoop_job_id, files_location, file_name,
                        original_path, created_at
                    ) VALUES (?, ?, ?, '', '', ?)
                """, ("job_csv", row["geoop_job_id"], loc, ts))
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1

    note_files = conn.execute("""
        SELECT geoop_job_id, geoop_note_id, files_location, file_name
        FROM geoop_staging_notes
        WHERE files_location IS NOT NULL AND files_location != ''
    """).fetchall()
    for row in note_files:
        loc = (row["files_location"] or "").strip().rstrip("/") + "/"
        fname = (row["file_name"] or "").strip()
        try:
            conn.execute("""
                INSERT OR IGNORE INTO geoop_staging_files (
                    source_type, geoop_job_id, geoop_note_id, files_location, file_name,
                    original_path, created_at
                ) VALUES (?, ?, ?, ?, ?, '', ?)
            """, ("note_csv", row["geoop_job_id"], row["geoop_note_id"], loc, fname, ts))
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1

    conn.commit()
    if close:
        conn.close()
    return {"inserted": inserted, "skipped": skipped}


def generate_diagnostics(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    diag = {}

    r = conn.execute("SELECT COUNT(*) c FROM geoop_staging_jobs").fetchone()
    diag["total_staged_jobs"] = r["c"]

    r = conn.execute("SELECT COUNT(DISTINCT geoop_job_id) c FROM geoop_staging_notes").fetchone()
    diag["total_staged_notes_unique_jobs"] = r["c"]

    r = conn.execute("SELECT COUNT(*) c FROM geoop_staging_notes").fetchone()
    diag["total_staged_notes"] = r["c"]

    r = conn.execute("SELECT COUNT(*) c FROM geoop_staging_files").fetchone()
    diag["total_file_records"] = r["c"]

    r = conn.execute("SELECT COUNT(*) c FROM geoop_staging_files WHERE source_type IN ('job_csv','note_csv')").fetchone()
    diag["manifest_records"] = r["c"]

    r = conn.execute("SELECT COUNT(*) c FROM geoop_staging_files WHERE found_on_disk=1").fetchone()
    diag["physical_files_scanned"] = r["c"]

    r = conn.execute("SELECT COUNT(*) c FROM geoop_staging_files WHERE found_on_disk=0").fetchone()
    diag["files_not_on_disk"] = r["c"]

    r = conn.execute("""
        SELECT file_hash, COUNT(*) c FROM geoop_staging_files
        WHERE file_hash IS NOT NULL AND file_hash != ''
        GROUP BY file_hash HAVING c > 1
    """).fetchall()
    diag["duplicate_files_by_hash"] = sum(row["c"] - 1 for row in r)
    diag["unique_hashes_with_dupes"] = len(r)

    r = conn.execute("""
        SELECT COUNT(*) c FROM geoop_staging_files
        WHERE source_type IN ('note_csv','job_csv') AND found_on_disk=1
    """).fetchone()
    diag["manifest_matched_to_physical"] = r["c"]

    r = conn.execute("""
        SELECT COUNT(*) c FROM geoop_staging_files
        WHERE source_type IN ('note_csv','job_csv') AND found_on_disk=0
    """).fetchone()
    diag["manifest_missing_physical"] = r["c"]

    r = conn.execute("""
        SELECT COUNT(*) c FROM geoop_staging_files
        WHERE source_type='disk_scan'
    """).fetchone()
    diag["physical_unmatched_to_manifest"] = r["c"]

    r = conn.execute("""
        SELECT COUNT(*) c FROM geoop_staging_files
        WHERE source_type = 'note_csv' AND found_on_disk=1
    """).fetchone()
    diag["note_files_matched_on_disk"] = r["c"]

    r = conn.execute("""
        SELECT COUNT(*) c FROM geoop_staging_notes
        WHERE geoop_job_id IN (SELECT geoop_job_id FROM geoop_staging_jobs)
    """).fetchone()
    diag["notes_matched_to_jobs"] = r["c"]

    r = conn.execute("""
        SELECT COUNT(*) c FROM geoop_staging_notes
        WHERE geoop_job_id NOT IN (SELECT geoop_job_id FROM geoop_staging_jobs)
    """).fetchone()
    diag["notes_unmatched_to_jobs"] = r["c"]

    status_counts = conn.execute("""
        SELECT status_label, COUNT(*) c FROM geoop_staging_jobs
        GROUP BY status_label ORDER BY c DESC
    """).fetchall()
    diag["job_status_breakdown"] = {row["status_label"]: row["c"] for row in status_counts}

    parse_stats = conn.execute("""
        SELECT
            COUNT(*) total,
            SUM(CASE WHEN parsed_client_name != '' THEN 1 ELSE 0 END) has_client,
            SUM(CASE WHEN parsed_account_number != '' THEN 1 ELSE 0 END) has_account,
            SUM(CASE WHEN parsed_regulation_type != '' THEN 1 ELSE 0 END) has_regulation,
            SUM(CASE WHEN parsed_amount_cents > 0 THEN 1 ELSE 0 END) has_amount,
            SUM(CASE WHEN parsed_reg != '' THEN 1 ELSE 0 END) has_reg,
            SUM(CASE WHEN parsed_vin != '' THEN 1 ELSE 0 END) has_vin,
            SUM(CASE WHEN parsed_deliver_to != '' THEN 1 ELSE 0 END) has_deliver,
            SUM(CASE WHEN parsed_security_make != '' THEN 1 ELSE 0 END) has_security_make,
            SUM(CASE WHEN parsed_costs_cents > 0 THEN 1 ELSE 0 END) has_costs
        FROM geoop_staging_jobs
    """).fetchone()
    diag["parse_coverage"] = {
        "total": parse_stats["total"],
        "client_name": parse_stats["has_client"],
        "account_number": parse_stats["has_account"],
        "regulation_type": parse_stats["has_regulation"],
        "amount": parse_stats["has_amount"],
        "registration": parse_stats["has_reg"],
        "vin": parse_stats["has_vin"],
        "deliver_to": parse_stats["has_deliver"],
        "security_make": parse_stats["has_security_make"],
        "costs": parse_stats["has_costs"],
    }

    note_types = conn.execute("""
        SELECT note_description, COUNT(*) c FROM geoop_staging_notes
        GROUP BY note_description ORDER BY c DESC LIMIT 20
    """).fetchall()
    diag["top_note_types"] = {row["note_description"][:80]: row["c"] for row in note_types}

    r = conn.execute("SELECT COUNT(*) c FROM geoop_staging_notes WHERE files_location != '' AND file_name != ''").fetchone()
    diag["notes_with_file_references"] = r["c"]

    if close:
        conn.close()
    return diag


STATUS_MAP = {
    "New": "New",
    "Active": "Active",
    "Active - PHONE WORK ONLY": "Active",
    "Completed": "Completed",
    "Invoiced": "Completed",
    "Cancelled": "Cancelled",
    "Suspended": "Suspended",
    "Awaiting advice from Client": "Awaiting info from client",
}


def _determine_job_type(title):
    title_lower = (title or "").lower()
    if "field call" in title_lower:
        return "Field Call"
    if "repo only" in title_lower:
        return "Repo Only"
    if "collect" in title_lower or "repo" in title_lower:
        return "Repo/Collect"
    if "process serve" in title_lower:
        return "Process Serve"
    return "Repo/Collect"


def import_staged_jobs(mode="insert_only", conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ts = _now()
    imported = 0
    skipped = 0
    updated = 0
    errors = 0
    error_list = []

    staged = conn.execute("""
        SELECT * FROM geoop_staging_jobs WHERE import_status='pending' ORDER BY id
    """).fetchall()

    for sj in staged:
        geoop_id = sj["geoop_job_id"]

        existing = conn.execute(
            "SELECT id FROM jobs WHERE internal_job_number=? OR client_job_number=?",
            (sj["reference_no"], geoop_id)
        ).fetchone()

        if existing and mode == "insert_only":
            conn.execute(
                "UPDATE geoop_staging_jobs SET import_status='skipped_exists', axion_job_id=?, imported_at=? WHERE id=?",
                (existing["id"], ts, sj["id"])
            )
            skipped += 1
            continue

        address_parts = [p for p in [sj["address"], sj["suburb"], sj["city"], sj["postcode"]] if p]
        full_address = ", ".join(address_parts)

        cust_id = None
        if sj["firstname"] or sj["lastname"]:
            fname = (sj["firstname"] or "").strip()
            lname = (sj["lastname"] or "").strip()

            cust = conn.execute(
                "SELECT id FROM customers WHERE first_name=? AND last_name=?",
                (fname, lname)
            ).fetchone()
            if cust:
                cust_id = cust["id"]
            else:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO customers (first_name, last_name, company, email, address, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?)
                """, (fname, lname, sj["company"] or "", sj["email"] or "", full_address, ts, ts))
                cust_id = cur.lastrowid

                mobile = (sj["mobile"] or "").strip()
                phone = (sj["phone"] or "").strip()
                if mobile:
                    conn.execute("""
                        INSERT INTO contact_phone_numbers (entity_type, entity_id, label, phone_number, created_at)
                        VALUES ('customer', ?, 'Mobile', ?, ?)
                    """, (cust_id, mobile, ts))
                if phone:
                    conn.execute("""
                        INSERT INTO contact_phone_numbers (entity_type, entity_id, label, phone_number, created_at)
                        VALUES ('customer', ?, 'Phone', ?, ?)
                    """, (cust_id, phone, ts))
                if sj["email"]:
                    conn.execute("""
                        INSERT INTO contact_emails (entity_type, entity_id, label, email, created_at)
                        VALUES ('customer', ?, 'Primary', ?, ?)
                    """, (cust_id, sj["email"], ts))

        status = STATUS_MAP.get(sj["status_label"], "New")
        job_type = _determine_job_type(sj["job_title"])

        if existing and mode == "update":
            conn.execute("""
                UPDATE jobs SET
                    status=?, job_address=?, description=?,
                    geoop_source_description=CASE WHEN (geoop_source_description IS NULL OR geoop_source_description='') THEN ? ELSE geoop_source_description END,
                    lender_name=?, account_number=?, regulation_type=?,
                    arrears_cents=?, costs_cents=?,
                    mmp_cents=?, job_due_date=?,
                    deliver_to=?, updated_at=?
                WHERE id=?
            """, (
                status, full_address, sj["raw_description"],
                sj["raw_description"],
                sj["parsed_client_name"] or "", sj["parsed_account_number"] or "",
                sj["parsed_regulation_type"] or "",
                sj["parsed_amount_cents"] or 0, sj["parsed_costs_cents"] or 0,
                sj["parsed_nmpd_amount_cents"] or 0, sj["parsed_nmpd_date"] or "",
                sj["parsed_deliver_to"] or "", ts,
                existing["id"]
            ))
            legacy_exists = conn.execute(
                "SELECT id FROM job_field_notes WHERE job_id=? AND note_type='geoop_import'",
                (existing["id"],)
            ).fetchone()
            if not legacy_exists and sj["raw_description"]:
                conn.execute("""
                    INSERT INTO job_field_notes (job_id, created_by_user_id, note_text, note_type, created_at)
                    VALUES (?, 1, ?, 'geoop_import', ?)
                """, (existing["id"], "[GeoOp Import] " + sj["raw_description"], ts))
            conn.execute(
                "UPDATE geoop_staging_jobs SET import_status='updated', axion_job_id=?, imported_at=? WHERE id=?",
                (existing["id"], ts, sj["id"])
            )
            updated += 1
            continue

        try:
            ref_no = sj["reference_no"] or geoop_id
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO jobs (
                    internal_job_number, display_ref, client_reference,
                    customer_id, job_type, visit_type, status, priority,
                    job_address, description, geoop_source_description,
                    lender_name, account_number, regulation_type,
                    arrears_cents, costs_cents, mmp_cents, job_due_date,
                    deliver_to, client_job_number,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                ref_no, ref_no, sj["parsed_account_number"] or "",
                cust_id, job_type, "New Visit", status, "Normal",
                full_address, sj["raw_description"], sj["raw_description"],
                sj["parsed_client_name"] or "", sj["parsed_account_number"] or "",
                sj["parsed_regulation_type"] or "",
                sj["parsed_amount_cents"] or 0, sj["parsed_costs_cents"] or 0,
                sj["parsed_nmpd_amount_cents"] or 0, sj["parsed_nmpd_date"] or "",
                sj["parsed_deliver_to"] or "", geoop_id,
                ts, ts
            ))
            axion_job_id = cur.lastrowid

            if sj["raw_description"]:
                conn.execute("""
                    INSERT INTO job_field_notes (job_id, created_by_user_id, note_text, note_type, created_at)
                    VALUES (?, 1, ?, 'geoop_import', ?)
                """, (axion_job_id, "[GeoOp Import] " + sj["raw_description"], ts))

            if sj["parsed_reg"] or sj["parsed_vin"] or sj["parsed_security_make"]:
                conn.execute("""
                    INSERT INTO job_items (
                        job_id, item_type, description, reg, vin,
                        make, model, year, colour, deliver_to,
                        lender_name, account_number, regulation_type,
                        created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    axion_job_id, "vehicle",
                    sj["parsed_security_description"] or "",
                    sj["parsed_reg"] or "",
                    sj["parsed_vin"] or "",
                    sj["parsed_security_make"] or "",
                    sj["parsed_security_model"] or "",
                    sj["parsed_security_year"] or "",
                    sj["parsed_security_colour"] or "",
                    sj["parsed_deliver_to"] or "",
                    sj["parsed_client_name"] or "",
                    sj["parsed_account_number"] or "",
                    sj["parsed_regulation_type"] or "",
                    ts
                ))

            conn.execute(
                "UPDATE geoop_staging_jobs SET import_status='imported', axion_job_id=?, axion_customer_id=?, imported_at=? WHERE id=?",
                (axion_job_id, cust_id, ts, sj["id"])
            )
            imported += 1
        except Exception as e:
            conn.execute(
                "UPDATE geoop_staging_jobs SET import_status='error', error_message=?, imported_at=? WHERE id=?",
                (str(e)[:500], ts, sj["id"])
            )
            errors += 1
            error_list.append({"geoop_id": geoop_id, "error": str(e)[:200]})

        if imported % 500 == 0:
            conn.commit()

    conn.commit()
    if close:
        conn.close()

    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "error_details": error_list[:50],
    }


_BACKFILL_BATCH_SIZE = 250


_ORPHAN_STALE_SECONDS = 7200


def recover_orphaned_backfill_runs():
    cutoff = _now()
    if isinstance(cutoff, str) and len(cutoff) >= 19:
        from datetime import datetime, timedelta
        try:
            dt = datetime.fromisoformat(cutoff)
            cutoff = (dt - timedelta(seconds=_ORPHAN_STALE_SECONDS)).isoformat(sep=" ", timespec="seconds")
        except Exception:
            cutoff = None
    else:
        cutoff = None

    conn = _db()
    try:
        if cutoff:
            orphans = conn.execute("""
                SELECT id, diagnostics_json FROM geoop_import_runs
                WHERE run_type='description_backfill' AND status='running'
                  AND completed_at IS NULL
                  AND started_at < ?
            """, (cutoff,)).fetchall()
        else:
            orphans = conn.execute("""
                SELECT id, diagnostics_json FROM geoop_import_runs
                WHERE run_type='description_backfill' AND status='running'
                  AND completed_at IS NULL
            """).fetchall()
        recovered = []
        for row in orphans:
            diag = {}
            if row["diagnostics_json"]:
                try:
                    diag = json.loads(row["diagnostics_json"])
                except Exception:
                    pass
            diag["status"] = "interrupted"
            diag["interrupted_reason"] = "orphaned_running_detected"
            conn.execute("""
                UPDATE geoop_import_runs
                SET status='interrupted', diagnostics_json=?, completed_at=?
                WHERE id=?
            """, (json.dumps(diag), _now(), row["id"]))
            recovered.append({
                "run_id": row["id"],
                "last_staging_id": diag.get("last_staging_id", 0),
                "batch_number": diag.get("batch_number", 0),
                "jobs_processed": diag.get("jobs_processed", 0),
            })
        if recovered:
            _retry_commit(conn)
        return recovered
    finally:
        conn.close()


def get_last_backfill_checkpoint():
    conn = _db()
    try:
        rows = conn.execute("""
            SELECT id, diagnostics_json FROM geoop_import_runs
            WHERE run_type='description_backfill'
              AND status IN ('interrupted', 'failed')
            ORDER BY id DESC LIMIT 5
        """).fetchall()
        for row in rows:
            if not row["diagnostics_json"]:
                continue
            try:
                diag = json.loads(row["diagnostics_json"])
            except Exception:
                continue
            last_id = diag.get("last_staging_id", 0)
            if last_id <= 0:
                continue
            return {
                "run_id": row["id"],
                "last_staging_id": last_id,
                "batch_number": diag.get("batch_number", 0),
                "jobs_processed": diag.get("jobs_processed", 0),
                "descriptions_preserved": diag.get("descriptions_preserved", 0),
                "legacy_notes_created": diag.get("legacy_notes_created", 0),
                "legacy_notes_already_exist": diag.get("legacy_notes_already_exist", 0),
                "job_items_updated": diag.get("job_items_updated", 0),
                "job_items_created": diag.get("job_items_created", 0),
                "fields_parsed": diag.get("fields_parsed", 0),
                "errors": diag.get("errors", 0),
            }
        return None
    finally:
        conn.close()


def _persist_backfill_progress(run_id, stats):
    if not run_id:
        return
    conn = _db()
    try:
        status = stats.get("status", "running")
        completed_at = _now() if status in ("completed", "failed") else None
        _retry_execute(conn, """
            UPDATE geoop_import_runs SET
            status=?, diagnostics_json=?, notes_imported=?, errors=?,
            completed_at=COALESCE(completed_at, ?)
            WHERE id=?
        """, (status, json.dumps(stats), stats.get("jobs_processed", 0),
              stats.get("errors", 0), completed_at, run_id))
        _retry_commit(conn)
    except Exception:
        pass
    finally:
        conn.close()


def get_backfill_progress(run_id):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT status, diagnostics_json FROM geoop_import_runs WHERE id=?", (run_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    result = {"status": row["status"]}
    if row["diagnostics_json"]:
        try:
            result.update(json.loads(row["diagnostics_json"]))
        except Exception:
            pass
    return result


def _backfill_one_job(conn, row, ts):
    axion_job_id = row["axion_job_id"]
    raw_desc = row["raw_description"]
    result = {"notes_created": 0, "already_ok": 0, "items_updated": 0,
              "items_created": 0, "desc_preserved": 0, "fields_parsed": 0}

    parsed = parse_description(raw_desc)
    has_parsed_fields = any(parsed.get(k) for k in (
        "parsed_client_name", "parsed_account_number", "parsed_regulation_type",
        "parsed_amount_cents", "parsed_costs_cents", "parsed_nmpd_amount_cents",
        "parsed_nmpd_date", "parsed_deliver_to"))
    if has_parsed_fields:
        result["fields_parsed"] = 1

    conn.execute("""
        UPDATE jobs SET
            geoop_source_description = CASE WHEN (geoop_source_description IS NULL OR geoop_source_description = '') THEN ? ELSE geoop_source_description END,
            lender_name = CASE WHEN (lender_name IS NULL OR lender_name = '') THEN ? ELSE lender_name END,
            account_number = CASE WHEN (account_number IS NULL OR account_number = '') THEN ? ELSE account_number END,
            regulation_type = CASE WHEN (regulation_type IS NULL OR regulation_type = '') THEN ? ELSE regulation_type END,
            arrears_cents = CASE WHEN (arrears_cents IS NULL OR arrears_cents = 0) THEN ? ELSE arrears_cents END,
            costs_cents = CASE WHEN (costs_cents IS NULL OR costs_cents = 0) THEN ? ELSE costs_cents END,
            mmp_cents = CASE WHEN (mmp_cents IS NULL OR mmp_cents = 0) THEN ? ELSE mmp_cents END,
            job_due_date = CASE WHEN (job_due_date IS NULL OR job_due_date = '') THEN ? ELSE job_due_date END,
            deliver_to = CASE WHEN (deliver_to IS NULL OR deliver_to = '') THEN ? ELSE deliver_to END,
            updated_at = ?
        WHERE id = ?
    """, (
        raw_desc,
        parsed.get("parsed_client_name", "") or "",
        parsed.get("parsed_account_number", "") or "",
        parsed.get("parsed_regulation_type", "") or "",
        parsed.get("parsed_amount_cents", 0) or 0,
        parsed.get("parsed_costs_cents", 0) or 0,
        parsed.get("parsed_nmpd_amount_cents", 0) or 0,
        parsed.get("parsed_nmpd_date", "") or "",
        parsed.get("parsed_deliver_to", "") or "",
        ts,
        axion_job_id
    ))
    result["desc_preserved"] = 1

    legacy_exists = conn.execute(
        "SELECT id FROM job_field_notes WHERE job_id=? AND note_type='geoop_import'",
        (axion_job_id,)
    ).fetchone()
    if not legacy_exists:
        conn.execute("""
            INSERT INTO job_field_notes (job_id, created_by_user_id, note_text, note_type, created_at)
            VALUES (?, 1, ?, 'geoop_import', ?)
        """, (axion_job_id, "[GeoOp Import] " + raw_desc, ts))
        result["notes_created"] = 1
    else:
        result["already_ok"] = 1

    p_reg = parsed.get("parsed_reg", "") or row["parsed_reg"] or ""
    p_vin = parsed.get("parsed_vin", "") or row["parsed_vin"] or ""
    p_make = parsed.get("parsed_security_make", "") or row["parsed_security_make"] or ""

    if p_reg or p_vin or p_make:
        existing_item = conn.execute(
            "SELECT id FROM job_items WHERE job_id=? AND item_type='vehicle'",
            (axion_job_id,)
        ).fetchone()
        if existing_item:
            conn.execute("""
                UPDATE job_items SET
                    reg = CASE WHEN (reg IS NULL OR reg = '') THEN ? ELSE reg END,
                    vin = CASE WHEN (vin IS NULL OR vin = '') THEN ? ELSE vin END,
                    make = CASE WHEN (make IS NULL OR make = '') THEN ? ELSE make END,
                    model = CASE WHEN (model IS NULL OR model = '') THEN ? ELSE model END,
                    year = CASE WHEN (year IS NULL OR year = '') THEN ? ELSE year END,
                    colour = CASE WHEN (colour IS NULL OR colour = '') THEN ? ELSE colour END,
                    description = CASE WHEN (description IS NULL OR description = '') THEN ? ELSE description END
                WHERE id = ?
            """, (
                p_reg, p_vin, p_make,
                parsed.get("parsed_security_model", "") or row["parsed_security_model"] or "",
                parsed.get("parsed_security_year", "") or row["parsed_security_year"] or "",
                parsed.get("parsed_security_colour", "") or row["parsed_security_colour"] or "",
                parsed.get("parsed_security_description", "") or row["parsed_security_description"] or "",
                existing_item["id"]
            ))
            result["items_updated"] = 1
        else:
            conn.execute("""
                INSERT INTO job_items (
                    job_id, item_type, description, reg, vin,
                    make, model, year, colour, deliver_to,
                    created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                axion_job_id, "vehicle",
                parsed.get("parsed_security_description", "") or row["parsed_security_description"] or "",
                p_reg, p_vin, p_make,
                parsed.get("parsed_security_model", "") or row["parsed_security_model"] or "",
                parsed.get("parsed_security_year", "") or row["parsed_security_year"] or "",
                parsed.get("parsed_security_colour", "") or row["parsed_security_colour"] or "",
                parsed.get("parsed_deliver_to", "") or row["parsed_deliver_to"] or "",
                ts
            ))
            result["items_created"] = 1

    return result


def backfill_geoop_descriptions(run_id=None, resume_checkpoint=None):
    ts = _now()
    stats = {
        "status": "running",
        "total_eligible": 0,
        "jobs_processed": 0,
        "descriptions_preserved": 0,
        "legacy_notes_created": 0,
        "legacy_notes_already_exist": 0,
        "job_items_updated": 0,
        "job_items_created": 0,
        "fields_parsed": 0,
        "errors": 0,
        "last_staging_id": 0,
        "batch_number": 0,
        "batch_size": _BACKFILL_BATCH_SIZE,
        "backfill_ts": ts,
        "resumed_from_run": None,
        "resumed_from_staging_id": 0,
    }

    if resume_checkpoint:
        for k in ("jobs_processed", "descriptions_preserved", "legacy_notes_created",
                   "legacy_notes_already_exist", "job_items_updated", "job_items_created",
                   "fields_parsed", "errors", "batch_number"):
            stats[k] = resume_checkpoint.get(k, 0)
        stats["last_staging_id"] = resume_checkpoint.get("last_staging_id", 0)
        stats["resumed_from_run"] = resume_checkpoint.get("run_id")
        stats["resumed_from_staging_id"] = resume_checkpoint.get("last_staging_id", 0)

    try:
        conn = _db()
        total = conn.execute("""
            SELECT COUNT(*) FROM geoop_staging_jobs sj
            WHERE sj.axion_job_id IS NOT NULL
              AND sj.import_status IN ('imported', 'updated', 'skipped_exists')
              AND sj.raw_description IS NOT NULL
              AND sj.raw_description != ''
        """).fetchone()[0]
        stats["total_eligible"] = total
        conn.close()

        _persist_backfill_progress(run_id, stats)

        last_id = stats["last_staging_id"]

        while True:
            conn = _db()
            try:
                rows = conn.execute("""
                    SELECT sj.id, sj.geoop_job_id, sj.axion_job_id, sj.raw_description,
                           sj.parsed_reg, sj.parsed_vin, sj.parsed_security_make,
                           sj.parsed_security_model, sj.parsed_security_year,
                           sj.parsed_security_colour, sj.parsed_security_description,
                           sj.parsed_deliver_to
                    FROM geoop_staging_jobs sj
                    WHERE sj.id > ?
                      AND sj.axion_job_id IS NOT NULL
                      AND sj.import_status IN ('imported', 'updated', 'skipped_exists')
                      AND sj.raw_description IS NOT NULL
                      AND sj.raw_description != ''
                    ORDER BY sj.id
                    LIMIT ?
                """, (last_id, _BACKFILL_BATCH_SIZE)).fetchall()

                if not rows:
                    conn.close()
                    break

                stats["batch_number"] += 1

                for row in rows:
                    last_id = row["id"]
                    try:
                        result = _backfill_one_job(conn, row, ts)
                        stats["jobs_processed"] += 1
                        stats["descriptions_preserved"] += result["desc_preserved"]
                        stats["legacy_notes_created"] += result["notes_created"]
                        stats["legacy_notes_already_exist"] += result["already_ok"]
                        stats["job_items_updated"] += result["items_updated"]
                        stats["job_items_created"] += result["items_created"]
                        stats["fields_parsed"] += result["fields_parsed"]
                    except Exception:
                        stats["errors"] += 1

                _retry_commit(conn)
                stats["last_staging_id"] = last_id
            finally:
                conn.close()

            _persist_backfill_progress(run_id, stats)

        stats["status"] = "completed"

    except Exception as e:
        stats["status"] = "failed"
        stats["error_message"] = str(e)[:500]

    _persist_backfill_progress(run_id, stats)
    return stats


def import_staged_notes(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ts = _now()
    imported = 0
    skipped = 0
    unmatched = 0
    errors = 0

    job_map = {}
    rows = conn.execute("SELECT geoop_job_id, axion_job_id FROM geoop_staging_jobs WHERE axion_job_id IS NOT NULL").fetchall()
    for r in rows:
        job_map[r["geoop_job_id"]] = r["axion_job_id"]

    batch_size = 5000
    while True:
        notes = conn.execute("""
            SELECT * FROM geoop_staging_notes WHERE import_status='pending'
            ORDER BY id LIMIT ?
        """, (batch_size,)).fetchall()

        if not notes:
            break

        for note in notes:
            axion_job_id = job_map.get(note["geoop_job_id"])
            if not axion_job_id:
                conn.execute(
                    "UPDATE geoop_staging_notes SET import_status='unmatched_job', imported_at=? WHERE id=?",
                    (ts, note["id"])
                )
                unmatched += 1
                continue

            note_text = (note["note_description"] or "").strip()
            if not note_text:
                conn.execute(
                    "UPDATE geoop_staging_notes SET import_status='skipped_empty', imported_at=? WHERE id=?",
                    (ts, note["id"])
                )
                skipped += 1
                continue

            note_date = note["file_date"] or ts
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(note_date.replace("Z", "+00:00"))
                note_date = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except (ValueError, AttributeError):
                note_date = ts

            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO job_field_notes (job_id, created_by_user_id, note_text, created_at, note_type)
                    VALUES (?, 1, ?, ?, 'text')
                """, (axion_job_id, note_text, note_date))
                note_id = cur.lastrowid

                conn.execute(
                    "UPDATE geoop_staging_notes SET import_status='imported', axion_job_id=?, axion_note_id=?, imported_at=? WHERE id=?",
                    (axion_job_id, note_id, ts, note["id"])
                )
                imported += 1
            except Exception as e:
                conn.execute(
                    "UPDATE geoop_staging_notes SET import_status='error', error_message=?, imported_at=? WHERE id=?",
                    (str(e)[:500], ts, note["id"])
                )
                errors += 1

        conn.commit()

    conn.commit()
    if close:
        conn.close()

    return {"imported": imported, "skipped": skipped, "unmatched": unmatched, "errors": errors}


def import_matched_files(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ts = _now()
    imported = 0
    skipped_dupe = 0
    skipped_no_disk = 0
    errors = 0

    job_map = {}
    rows = conn.execute("SELECT geoop_job_id, axion_job_id FROM geoop_staging_jobs WHERE axion_job_id IS NOT NULL").fetchall()
    for r in rows:
        job_map[r["geoop_job_id"]] = r["axion_job_id"]

    seen_hashes = set()
    existing_hashes = conn.execute("""
        SELECT DISTINCT file_hash FROM geoop_staging_files
        WHERE import_status='imported' AND file_hash IS NOT NULL
    """).fetchall()
    for r in existing_hashes:
        seen_hashes.add(r["file_hash"])

    files = conn.execute("""
        SELECT * FROM geoop_staging_files
        WHERE found_on_disk=1 AND import_status='pending'
        ORDER BY id
    """).fetchall()

    for f in files:
        axion_job_id = job_map.get(f["geoop_job_id"])
        if not axion_job_id:
            note_row = conn.execute(
                "SELECT axion_job_id FROM geoop_staging_notes WHERE geoop_note_id=? AND axion_job_id IS NOT NULL",
                (f["geoop_note_id"] or "",)
            ).fetchone()
            if note_row:
                axion_job_id = note_row["axion_job_id"]

        if not axion_job_id:
            conn.execute(
                "UPDATE geoop_staging_files SET import_status='unmatched', imported_at=? WHERE id=?",
                (ts, f["id"])
            )
            skipped_no_disk += 1
            continue

        if f["file_hash"] and f["file_hash"] in seen_hashes:
            conn.execute(
                "UPDATE geoop_staging_files SET import_status='deduplicated', deduplicated=1, imported_at=? WHERE id=?",
                (ts, f["id"])
            )
            skipped_dupe += 1
            continue

        disk_path = f["disk_path"]
        if not disk_path or not os.path.exists(disk_path):
            conn.execute(
                "UPDATE geoop_staging_files SET import_status='file_missing', imported_at=? WHERE id=?",
                (ts, f["id"])
            )
            skipped_no_disk += 1
            continue

        original_name = f["file_name"] or os.path.basename(disk_path)
        ext = os.path.splitext(original_name)[1] if original_name else ""
        stored_name = f"{uuid.uuid4().hex}{ext}"
        dest = os.path.join(UPLOAD_FOLDER, stored_name)

        try:
            shutil.copy2(disk_path, dest)
            mime = f["mime_type"] or mimetypes.guess_type(original_name)[0] or "application/octet-stream"

            cur = conn.cursor()
            cur.execute("""
                INSERT INTO job_documents (
                    job_id, doc_type, title, original_filename, stored_filename,
                    mime_type, uploaded_by_user_id, uploaded_at
                ) VALUES (?, 'GeoOp Import', ?, ?, ?, ?, 1, ?)
            """, (axion_job_id, original_name, original_name, stored_name, mime, ts))
            doc_id = cur.lastrowid

            conn.execute(
                "UPDATE geoop_staging_files SET import_status='imported', axion_doc_id=?, stored_filename=?, imported_at=? WHERE id=?",
                (doc_id, stored_name, ts, f["id"])
            )
            if f["file_hash"]:
                seen_hashes.add(f["file_hash"])
            imported += 1
        except Exception as e:
            conn.execute(
                "UPDATE geoop_staging_files SET import_status='error', error_message=?, imported_at=? WHERE id=?",
                (str(e)[:500], ts, f["id"])
            )
            errors += 1

        if imported % 200 == 0:
            conn.commit()

    conn.commit()
    if close:
        conn.close()

    return {"imported": imported, "deduplicated": skipped_dupe, "unmatched": skipped_no_disk, "errors": errors}


_RETRY_MAX = 5
_RETRY_BASE_DELAY = 0.5


def _retry_execute(conn, sql, params=(), retries=_RETRY_MAX):
    import time
    for attempt in range(retries):
        try:
            return conn.execute(sql, params)
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < retries - 1:
                time.sleep(_RETRY_BASE_DELAY * (2 ** attempt))
                continue
            raise


def _retry_commit(conn, retries=_RETRY_MAX):
    import time
    for attempt in range(retries):
        try:
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < retries - 1:
                time.sleep(_RETRY_BASE_DELAY * (2 ** attempt))
                continue
            raise


def get_azure_scan_progress(run_id):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT status, diagnostics_json FROM geoop_import_runs WHERE id=?", (run_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    result = {"status": row["status"]}
    if row["diagnostics_json"]:
        try:
            result.update(json.loads(row["diagnostics_json"]))
        except Exception:
            pass
    return result


def _persist_scan_progress(run_id, stats):
    if not run_id:
        return
    conn = _db()
    try:
        _retry_execute(conn, """
            UPDATE geoop_import_runs SET
            diagnostics_json=?, notes_imported=?, errors=?
            WHERE id=?
        """, (json.dumps(stats), stats.get("attachments_linked", 0),
              stats.get("errors", 0), run_id))
        _retry_commit(conn)
    except Exception:
        pass
    finally:
        conn.close()


def scan_azure_blob_attachments(container_sas_url, upload_fn=None, run_id=None,
                                 blob_prefix=None):
    import time
    from azure.storage.blob import ContainerClient

    ts = _now()
    container_client = ContainerClient.from_container_url(container_sas_url)

    conn = _db()
    try:
        ensure_staging_tables(conn)

        job_map = {}
        rows = conn.execute(
            "SELECT geoop_job_id, axion_job_id FROM geoop_staging_jobs WHERE axion_job_id IS NOT NULL"
        ).fetchall()
        for r in rows:
            job_map[r["geoop_job_id"]] = r["axion_job_id"]

        note_map = {}
        rows = conn.execute(
            "SELECT geoop_note_id, axion_note_id, geoop_job_id FROM geoop_staging_notes WHERE axion_note_id IS NOT NULL"
        ).fetchall()
        for r in rows:
            note_map[r["geoop_note_id"]] = {
                "axion_note_id": r["axion_note_id"],
                "geoop_job_id": r["geoop_job_id"],
            }

        existing_hashes = set()
        for r in conn.execute(
            "SELECT DISTINCT file_hash FROM geoop_staging_files WHERE import_status='imported' AND file_hash IS NOT NULL"
        ).fetchall():
            existing_hashes.add(r["file_hash"])
        for r in conn.execute(
            "SELECT DISTINCT file_hash FROM geoop_staging_files WHERE file_hash IS NOT NULL AND found_on_disk=1"
        ).fetchall():
            existing_hashes.add(r["file_hash"])
    finally:
        conn.close()

    stats = {
        "blobs_scanned": 0,
        "files_processed": 0,
        "attachments_linked": 0,
        "skipped_no_match": 0,
        "skipped_duplicate": 0,
        "skipped_no_note": 0,
        "errors": 0,
        "zip_files_processed": 0,
        "zip_entries_scanned": 0,
        "attachments_matched": 0,
        "status": "running",
        "scan_ts": ts,
    }

    stats["phase"] = "listing_blobs"
    _persist_scan_progress(run_id, stats)

    write_batch = []
    unmatched_batch = []
    current_zip = [None]

    def _flush_unmatched():
        if not unmatched_batch:
            return
        uconn = _db()
        try:
            for u in unmatched_batch:
                _retry_execute(uconn, """
                    INSERT INTO geoop_unmatched_attachments
                    (run_id, zip_name, entry_path, filename, geoop_job_id, geoop_note_id, reason, created_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (run_id, u["zip_name"], u["entry_path"], u["filename"],
                      u["geoop_job_id"], u["geoop_note_id"], u["reason"], ts))
            _retry_commit(uconn)
        finally:
            uconn.close()
        unmatched_batch.clear()

    def _log_unmatched(entry_path, filename, geoop_job_id, geoop_note_id, reason):
        unmatched_batch.append({
            "zip_name": current_zip[0],
            "entry_path": entry_path,
            "filename": filename or "",
            "geoop_job_id": geoop_job_id or "",
            "geoop_note_id": geoop_note_id or "",
            "reason": reason,
        })
        if len(unmatched_batch) >= 100:
            _flush_unmatched()

    def _process_file(data_bytes, filename, geoop_job_id, geoop_note_id, blob_path):
        file_hash = hashlib.md5(data_bytes).hexdigest()

        if file_hash in existing_hashes:
            stats["skipped_duplicate"] += 1
            return

        axion_job_id = job_map.get(geoop_job_id)
        note_info = note_map.get(geoop_note_id)

        if not axion_job_id and note_info:
            axion_job_id = job_map.get(note_info["geoop_job_id"])

        if not axion_job_id:
            stats["skipped_no_match"] += 1
            _log_unmatched(blob_path, filename, geoop_job_id, geoop_note_id, "no_matching_job")
            return

        axion_note_id = note_info["axion_note_id"] if note_info else None

        if not axion_note_id:
            stats["skipped_no_note"] += 1
            _log_unmatched(blob_path, filename, geoop_job_id, geoop_note_id, "no_matching_note")
            return

        stats["attachments_matched"] += 1

        ext = os.path.splitext(filename)[1] if filename else ""
        stored_name = f"{uuid.uuid4().hex}{ext}"
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        fsize = len(data_bytes)

        try:
            if upload_fn:
                upload_fn(data_bytes, stored_name, mime)
            else:
                dest = os.path.join(UPLOAD_FOLDER, stored_name)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as fh:
                    fh.write(data_bytes)

            files_loc = "/".join(blob_path.replace("\\", "/").split("/")[:-1]) + "/"
            write_batch.append({
                "axion_note_id": axion_note_id,
                "stored_name": stored_name,
                "geoop_job_id": geoop_job_id,
                "geoop_note_id": geoop_note_id,
                "files_loc": files_loc,
                "filename": filename,
                "blob_path": blob_path,
                "file_hash": file_hash,
                "fsize": fsize,
                "mime": mime,
            })

            existing_hashes.add(file_hash)
            stats["attachments_linked"] += 1
        except Exception:
            stats["errors"] += 1

    def _flush_batch():
        if not write_batch:
            return
        wconn = _db()
        try:
            for item in write_batch:
                _retry_execute(wconn, """
                    INSERT INTO job_note_files (job_field_note_id, filename, filepath, uploaded_at)
                    VALUES (?, ?, ?, ?)
                """, (item["axion_note_id"], item["stored_name"], item["stored_name"], ts))

                try:
                    _retry_execute(wconn, """
                        INSERT OR IGNORE INTO geoop_staging_files (
                            source_type, geoop_job_id, geoop_note_id, files_location, file_name,
                            original_path, file_hash, file_size, mime_type, found_on_disk, disk_path,
                            import_status, stored_filename, imported_at, created_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,1,?,'imported',?,?,?)
                    """, (
                        "azure_blob", item["geoop_job_id"], item["geoop_note_id"],
                        item["files_loc"], item["filename"],
                        item["blob_path"], item["file_hash"], item["fsize"], item["mime"],
                        item["stored_name"], item["stored_name"], ts, ts
                    ))
                except sqlite3.IntegrityError:
                    pass
            _retry_commit(wconn)
        finally:
            wconn.close()
        write_batch.clear()

    try:
        stats["phase"] = "counting_blobs"
        _persist_scan_progress(run_id, stats)
        total_blobs = 0
        blob_names_cache = []
        for b in container_client.list_blobs(name_starts_with=blob_prefix):
            total_blobs += 1
            blob_names_cache.append(b.name)
        stats["total_blobs_in_container"] = total_blobs
        stats["phase"] = "listing_blobs"
        _persist_scan_progress(run_id, stats)

        def _parse_attachment_path(path_str):
            parts = path_str.replace("\\", "/").split("/")
            if len(parts) < 4:
                return None
            att_idx = None
            for i, p in enumerate(parts):
                if p == "attachments":
                    att_idx = i
                    break
            if att_idx is None or len(parts) < att_idx + 4:
                return None
            geoop_job_id = parts[att_idx + 1]
            geoop_note_id = parts[att_idx + 2]
            if not geoop_job_id or not geoop_note_id:
                return None
            raw_filename = parts[-1]
            underscore_idx = raw_filename.find("_")
            filename = raw_filename[underscore_idx + 1:] if underscore_idx > 0 else raw_filename
            if not filename:
                return None
            return geoop_job_id, geoop_note_id, filename

        class _AzureBlobFile:
            _BUF_SIZE = 4 * 1024 * 1024

            def __init__(self, blob_client_obj):
                self._client = blob_client_obj
                props = blob_client_obj.get_blob_properties()
                self._size = props.size
                self._pos = 0
                self._buf = b""
                self._buf_start = 0

            def read(self, n=-1):
                if self._pos >= self._size:
                    return b""
                if n == -1 or n is None:
                    n = self._size - self._pos
                buf_end = self._buf_start + len(self._buf)
                if self._buf and self._buf_start <= self._pos < buf_end:
                    off = self._pos - self._buf_start
                    avail = len(self._buf) - off
                    if avail >= n:
                        self._pos += n
                        return self._buf[off:off + n]
                remaining = min(n, self._size - self._pos)
                parts = []
                fetched = 0
                while fetched < remaining:
                    chunk_size = min(self._BUF_SIZE, remaining - fetched)
                    data = self._client.download_blob(
                        offset=self._pos + fetched, length=chunk_size
                    ).readall()
                    if not data:
                        break
                    parts.append(data)
                    fetched += len(data)
                result = b"".join(parts)
                if len(result) <= self._BUF_SIZE:
                    self._buf = result
                    self._buf_start = self._pos
                else:
                    self._buf = b""
                    self._buf_start = 0
                self._pos += len(result)
                return result

            def seek(self, offset, whence=0):
                if whence == 0:
                    self._pos = offset
                elif whence == 1:
                    self._pos += offset
                elif whence == 2:
                    self._pos = self._size + offset
                self._pos = max(0, min(self._pos, self._size))
                return self._pos

            def tell(self):
                return self._pos

            def seekable(self):
                return True

            def readable(self):
                return True

        for blob_name in blob_names_cache:
            stats["blobs_scanned"] += 1
            blob_basename = os.path.basename(blob_name)
            is_root_zip = blob_basename.lower().endswith(".zip") and "/" not in blob_name.strip("/")

            if is_root_zip:
                stats["phase"] = "starting_blob"
                stats["current_blob"] = blob_basename
                current_zip[0] = blob_basename
                _persist_scan_progress(run_id, stats)
                try:
                    blob_client = container_client.get_blob_client(blob_name)
                    blob_props = blob_client.get_blob_properties()
                    blob_size_mb = round(blob_props.size / (1024 * 1024), 1)

                    stats["phase"] = "streaming_zip"
                    stats["blob_size_mb"] = blob_size_mb
                    _persist_scan_progress(run_id, stats)

                    blob_file = _AzureBlobFile(blob_client)
                    with zipfile.ZipFile(blob_file) as zf:
                        stats["zip_files_processed"] += 1
                        stats["files_processed"] += 1
                        entries = [e for e in zf.namelist() if not e.endswith("/")]
                        stats["zip_entries_total"] = len(entries)
                        stats["zip_entries_processed"] = 0
                        if "zip_summaries" not in stats:
                            stats["zip_summaries"] = {}
                        stats["zip_summaries"][blob_basename] = {"total_entries": len(entries)}
                        _persist_scan_progress(run_id, stats)

                        stats["phase"] = "extracting_entries"
                        zip_matched = 0
                        zip_linked = 0
                        zip_dupes = 0
                        zip_no_match = 0
                        zip_no_note = 0
                        zip_parse_fail = 0
                        zip_errors = 0

                        for entry in entries:
                            stats["zip_entries_scanned"] += 1
                            parsed = _parse_attachment_path(entry)
                            if not parsed:
                                stats["skipped_no_match"] += 1
                                zip_parse_fail += 1
                                stats["zip_entries_processed"] += 1
                                _log_unmatched(
                                    blob_name + "/" + entry, os.path.basename(entry),
                                    None, None, "path_parse_failed"
                                )
                                continue
                            entry_job_id, entry_note_id, entry_filename = parsed

                            pre_linked = stats["attachments_linked"]
                            pre_no_match = stats["skipped_no_match"]
                            pre_no_note = stats["skipped_no_note"]
                            pre_dupes = stats["skipped_duplicate"]

                            try:
                                entry_data = zf.read(entry)
                                _process_file(
                                    entry_data, entry_filename,
                                    entry_job_id, entry_note_id,
                                    blob_name + "/" + entry
                                )
                            except Exception as entry_err:
                                stats["errors"] += 1
                                zip_errors += 1
                                stats["last_error"] = f"entry {entry}: {str(entry_err)[:200]}"

                            if stats["attachments_linked"] > pre_linked:
                                zip_linked += 1
                                zip_matched += 1
                            elif stats["skipped_duplicate"] > pre_dupes:
                                zip_dupes += 1
                            elif stats["skipped_no_match"] > pre_no_match:
                                zip_no_match += 1
                            elif stats["skipped_no_note"] > pre_no_note:
                                zip_no_note += 1

                            stats["zip_entries_processed"] += 1

                            if len(write_batch) >= 25:
                                _flush_batch()
                            if stats["zip_entries_processed"] % 200 == 0:
                                _persist_scan_progress(run_id, stats)

                    _flush_batch()
                    _flush_unmatched()
                    stats["zip_summaries"][blob_basename].update({
                        "matched": zip_matched,
                        "linked": zip_linked,
                        "duplicates": zip_dupes,
                        "no_matching_job": zip_no_match,
                        "no_matching_note": zip_no_note,
                        "path_parse_failed": zip_parse_fail,
                        "errors": zip_errors,
                    })
                except zipfile.BadZipFile as bze:
                    stats["errors"] += 1
                    stats["last_error"] = f"BadZipFile: {blob_basename}: {str(bze)[:200]}"
                except Exception as ze:
                    stats["errors"] += 1
                    stats["last_error"] = f"{blob_basename}: {str(ze)[:300]}"
                current_zip[0] = None
                stats.pop("current_blob", None)
                stats.pop("blob_size_mb", None)
                stats.pop("zip_entries_total", None)
                stats.pop("zip_entries_processed", None)
                _persist_scan_progress(run_id, stats)
                continue

            parsed = _parse_attachment_path(blob_name)
            if not parsed:
                stats["skipped_no_match"] += 1
                _log_unmatched(blob_name, blob_basename, None, None, "path_parse_failed")
                continue
            geoop_job_id, geoop_note_id, filename = parsed

            is_zip = blob_basename.lower().endswith(".zip")

            stats["phase"] = "processing_blob"
            stats["current_blob"] = blob_basename

            try:
                blob_client = container_client.get_blob_client(blob_name)
                download_stream = blob_client.download_blob()
            except Exception:
                stats["errors"] += 1
                continue

            stats["files_processed"] += 1

            if is_zip:
                try:
                    buf = io.BytesIO()
                    for chunk in download_stream.chunks():
                        buf.write(chunk)
                    buf.seek(0)
                    with zipfile.ZipFile(buf) as zf:
                        stats["zip_files_processed"] += 1
                        for entry in zf.namelist():
                            if entry.endswith("/"):
                                continue
                            entry_name = os.path.basename(entry)
                            if not entry_name:
                                continue
                            try:
                                entry_data = zf.read(entry)
                                _process_file(
                                    entry_data, entry_name,
                                    geoop_job_id, geoop_note_id, blob_name + "/" + entry
                                )
                            except Exception:
                                stats["errors"] += 1
                except zipfile.BadZipFile:
                    buf.seek(0)
                    blob_data = buf.read()
                    _process_file(blob_data, filename, geoop_job_id, geoop_note_id, blob_name)
            else:
                blob_data = download_stream.readall()
                _process_file(blob_data, filename, geoop_job_id, geoop_note_id, blob_name)

            stats.pop("current_blob", None)

            if len(write_batch) >= 25:
                _flush_batch()

            if stats["blobs_scanned"] % 50 == 0:
                _persist_scan_progress(run_id, stats)

        _flush_batch()
        _flush_unmatched()
        stats["status"] = "completed"

    except Exception as e:
        _flush_batch()
        _flush_unmatched()
        stats["status"] = "failed"
        stats["error_message"] = str(e)[:500]

    _persist_scan_progress(run_id, stats)

    return stats


def get_unmatched_report(run_id):
    conn = _db()
    try:
        rows = conn.execute("""
            SELECT zip_name, entry_path, filename, geoop_job_id, geoop_note_id, reason
            FROM geoop_unmatched_attachments
            WHERE run_id=?
            ORDER BY reason, entry_path
        """, (run_id,)).fetchall()
    finally:
        conn.close()

    summary = {}
    entries = []
    for r in rows:
        reason = r["reason"]
        summary[reason] = summary.get(reason, 0) + 1
        entries.append({
            "zip_name": r["zip_name"] or "",
            "entry_path": r["entry_path"],
            "filename": r["filename"] or "",
            "geoop_job_id": r["geoop_job_id"] or "",
            "geoop_note_id": r["geoop_note_id"] or "",
            "reason": reason,
        })

    return {"total": len(entries), "by_reason": summary, "entries": entries}


def get_scan_samples(run_id, unmatched_limit=10, matched_limit=5):
    conn = _db()
    try:
        unmatched = conn.execute("""
            SELECT zip_name, entry_path, filename, geoop_job_id, geoop_note_id, reason
            FROM geoop_unmatched_attachments
            WHERE run_id=?
            ORDER BY RANDOM()
            LIMIT ?
        """, (run_id, unmatched_limit)).fetchall()

        run_row = conn.execute(
            "SELECT diagnostics_json FROM geoop_import_runs WHERE id=?", (run_id,)
        ).fetchone()
        scan_ts = None
        if run_row and run_row["diagnostics_json"]:
            try:
                diag = json.loads(run_row["diagnostics_json"])
                scan_ts = diag.get("scan_ts")
            except Exception:
                pass

        matched = []
        if scan_ts:
            matched = conn.execute("""
                SELECT sf.original_path, sf.geoop_job_id, sf.geoop_note_id,
                       sf.file_name, sf.stored_filename,
                       j.internal_job_number AS job_ref,
                       j.job_address
                FROM geoop_staging_files sf
                LEFT JOIN geoop_staging_jobs sj ON sj.geoop_job_id = sf.geoop_job_id
                LEFT JOIN jobs j ON j.id = sj.axion_job_id
                WHERE sf.source_type = 'azure_blob'
                  AND sf.import_status = 'imported'
                  AND sf.imported_at = ?
                ORDER BY RANDOM()
                LIMIT ?
            """, (scan_ts, matched_limit)).fetchall()
    finally:
        conn.close()

    return {
        "unmatched_samples": [
            {
                "zip_name": r["zip_name"] or "",
                "entry_path": r["entry_path"],
                "reason": r["reason"],
            }
            for r in unmatched
        ],
        "matched_samples": [
            {
                "source_path": r["original_path"] or "",
                "filename": r["file_name"] or "",
                "job_ref": r["job_ref"] or "",
                "job_address": r["job_address"] or "",
                "geoop_job_id": r["geoop_job_id"] or "",
                "geoop_note_id": r["geoop_note_id"] or "",
            }
            for r in matched
        ],
    }


def get_backfill_samples(run_id, limit=5):
    conn = _db()
    try:
        run_row = conn.execute(
            "SELECT started_at, diagnostics_json FROM geoop_import_runs WHERE id=?", (run_id,)
        ).fetchone()
        if not run_row:
            return None

        diag = {}
        backfill_ts = None
        if run_row["diagnostics_json"]:
            try:
                diag = json.loads(run_row["diagnostics_json"])
                backfill_ts = diag.get("backfill_ts")
            except Exception:
                pass

        if not backfill_ts:
            backfill_ts = run_row["started_at"]

        samples = conn.execute("""
            SELECT sj.geoop_job_id, sj.reference_no, sj.raw_description,
                   sj.axion_job_id,
                   j.geoop_source_description,
                   j.lender_name, j.account_number, j.regulation_type,
                   j.arrears_cents, j.costs_cents, j.mmp_cents,
                   j.job_due_date, j.deliver_to, j.internal_job_number,
                   fn.note_text AS legacy_note,
                   ji.reg, ji.vin, ji.make, ji.model, ji.year, ji.colour
            FROM geoop_staging_jobs sj
            JOIN jobs j ON j.id = sj.axion_job_id
            LEFT JOIN job_field_notes fn ON fn.job_id = sj.axion_job_id AND fn.note_type = 'geoop_import'
            LEFT JOIN job_items ji ON ji.job_id = sj.axion_job_id AND ji.item_type = 'vehicle'
            WHERE sj.axion_job_id IS NOT NULL
              AND sj.raw_description IS NOT NULL
              AND sj.raw_description != ''
              AND j.geoop_source_description IS NOT NULL
              AND j.geoop_source_description != ''
              AND j.updated_at = ?
            ORDER BY RANDOM()
            LIMIT ?
        """, (backfill_ts, limit)).fetchall()

        total_with_desc = conn.execute("""
            SELECT COUNT(*) FROM jobs j
            JOIN geoop_staging_jobs sj ON sj.axion_job_id = j.id
            WHERE j.geoop_source_description IS NOT NULL AND j.geoop_source_description != ''
              AND j.updated_at = ?
        """, (backfill_ts,)).fetchone()[0]

        total_legacy_notes = conn.execute("""
            SELECT COUNT(*) FROM job_field_notes
            WHERE note_type = 'geoop_import' AND created_at = ?
        """, (backfill_ts,)).fetchone()[0]

        total_items = conn.execute("""
            SELECT COUNT(*) FROM job_items ji
            JOIN geoop_staging_jobs sj ON ji.job_id = sj.axion_job_id
            JOIN jobs j ON j.id = sj.axion_job_id
            WHERE ji.item_type = 'vehicle' AND sj.axion_job_id IS NOT NULL
              AND j.updated_at = ?
        """, (backfill_ts,)).fetchone()[0]

        fields_populated = conn.execute("""
            SELECT
                SUM(CASE WHEN j.lender_name IS NOT NULL AND j.lender_name != '' THEN 1 ELSE 0 END) AS lender,
                SUM(CASE WHEN j.account_number IS NOT NULL AND j.account_number != '' THEN 1 ELSE 0 END) AS account,
                SUM(CASE WHEN j.regulation_type IS NOT NULL AND j.regulation_type != '' THEN 1 ELSE 0 END) AS regulation,
                SUM(CASE WHEN j.arrears_cents > 0 THEN 1 ELSE 0 END) AS arrears,
                SUM(CASE WHEN j.costs_cents > 0 THEN 1 ELSE 0 END) AS costs,
                SUM(CASE WHEN j.mmp_cents > 0 THEN 1 ELSE 0 END) AS mmp,
                SUM(CASE WHEN j.job_due_date IS NOT NULL AND j.job_due_date != '' THEN 1 ELSE 0 END) AS due_date
            FROM jobs j
            JOIN geoop_staging_jobs sj ON sj.axion_job_id = j.id
            WHERE sj.axion_job_id IS NOT NULL
              AND sj.raw_description IS NOT NULL AND sj.raw_description != ''
              AND j.updated_at = ?
        """, (backfill_ts,)).fetchone()

    finally:
        conn.close()

    def _cents_to_str(v):
        if not v:
            return ""
        return f"${v/100:,.2f}"

    return {
        "run_summary": diag,
        "totals": {
            "descriptions_preserved": total_with_desc,
            "legacy_notes_created": total_legacy_notes,
            "security_items": total_items,
            "fields_populated": {
                "lender_name": fields_populated["lender"] or 0,
                "account_number": fields_populated["account"] or 0,
                "regulation_type": fields_populated["regulation"] or 0,
                "arrears": fields_populated["arrears"] or 0,
                "costs": fields_populated["costs"] or 0,
                "mmp": fields_populated["mmp"] or 0,
                "due_date": fields_populated["due_date"] or 0,
            },
        },
        "samples": [
            {
                "job_ref": r["internal_job_number"] or r["reference_no"] or "",
                "geoop_job_id": r["geoop_job_id"] or "",
                "raw_description": (r["raw_description"] or "")[:500],
                "legacy_note": (r["legacy_note"] or "")[:500],
                "preserved_source": (r["geoop_source_description"] or "")[:500],
                "lender_name": r["lender_name"] or "",
                "account_number": r["account_number"] or "",
                "regulation_type": r["regulation_type"] or "",
                "arrears": _cents_to_str(r["arrears_cents"]),
                "costs": _cents_to_str(r["costs_cents"]),
                "mmp": _cents_to_str(r["mmp_cents"]),
                "due_date": r["job_due_date"] or "",
                "deliver_to": r["deliver_to"] or "",
                "vehicle": {
                    "reg": r["reg"] or "",
                    "vin": r["vin"] or "",
                    "make": r["make"] or "",
                    "model": r["model"] or "",
                    "year": r["year"] or "",
                    "colour": r["colour"] or "",
                } if r["reg"] or r["vin"] or r["make"] else None,
            }
            for r in samples
        ],
    }


def reset_staging(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    conn.execute("DELETE FROM geoop_staging_jobs")
    conn.execute("DELETE FROM geoop_staging_notes")
    conn.execute("DELETE FROM geoop_staging_files")
    try:
        conn.execute("DELETE FROM geoop_notes_rejects")
    except Exception:
        pass
    conn.commit()

    if close:
        conn.close()


def dry_run_report(jobs_csv=None, notes_csv=None, attachment_dirs=None):
    conn = _db()
    ensure_staging_tables(conn)

    report = {"steps": [], "diagnostics": {}}

    if jobs_csv and os.path.exists(jobs_csv):
        result = stage_jobs_csv(jobs_csv, conn)
        report["steps"].append({"step": "stage_jobs", "result": result})

    if notes_csv and os.path.exists(notes_csv):
        result = stage_notes_csv(notes_csv, conn)
        report["steps"].append({"step": "stage_notes", "result": result})

    build_file_manifest_from_csv(conn)

    if attachment_dirs:
        valid_dirs = [d for d in attachment_dirs if os.path.isdir(d)]
        if valid_dirs:
            result = scan_attachment_dirs(valid_dirs, conn)
            report["steps"].append({"step": "scan_attachments", "result": result})

    diag = generate_diagnostics(conn)
    report["diagnostics"] = diag

    sample_jobs = conn.execute("""
        SELECT geoop_job_id, reference_no, job_title, status_label,
               parsed_client_name, parsed_account_number, parsed_regulation_type,
               parsed_amount_type, parsed_amount_cents, parsed_reg, parsed_vin,
               parsed_security_make, parsed_security_model, parsed_deliver_to
        FROM geoop_staging_jobs ORDER BY id LIMIT 10
    """).fetchall()
    report["sample_parsed_jobs"] = [dict(r) for r in sample_jobs]

    conn.close()
    return report
