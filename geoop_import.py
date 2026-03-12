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
                    lender_name=?, account_number=?, regulation_type=?,
                    arrears_cents=?, costs_cents=?,
                    deliver_to=?, updated_at=?
                WHERE id=?
            """, (
                status, full_address, sj["raw_description"],
                sj["parsed_client_name"] or "", sj["parsed_account_number"] or "",
                sj["parsed_regulation_type"] or "",
                sj["parsed_amount_cents"] or 0, sj["parsed_costs_cents"] or 0,
                sj["parsed_deliver_to"] or "", ts,
                existing["id"]
            ))
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
                    job_address, description,
                    lender_name, account_number, regulation_type,
                    arrears_cents, costs_cents,
                    deliver_to, client_job_number,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                ref_no, ref_no, sj["parsed_account_number"] or "",
                cust_id, job_type, "New Visit", status, "Normal",
                full_address, sj["raw_description"],
                sj["parsed_client_name"] or "", sj["parsed_account_number"] or "",
                sj["parsed_regulation_type"] or "",
                sj["parsed_amount_cents"] or 0, sj["parsed_costs_cents"] or 0,
                sj["parsed_deliver_to"] or "", geoop_id,
                ts, ts
            ))
            axion_job_id = cur.lastrowid

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
        "status": "running",
    }

    stats["phase"] = "listing_blobs"
    _persist_scan_progress(run_id, stats)

    write_batch = []

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
            return

        axion_note_id = note_info["axion_note_id"] if note_info else None

        if not axion_note_id:
            stats["skipped_no_note"] += 1
            return

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

        import tempfile

        for blob_name in blob_names_cache:
            stats["blobs_scanned"] += 1
            blob_basename = os.path.basename(blob_name)
            is_root_zip = blob_basename.lower().endswith(".zip") and "/" not in blob_name.strip("/")

            if is_root_zip:
                stats["phase"] = "starting_blob"
                stats["current_blob"] = blob_basename
                _persist_scan_progress(run_id, stats)
                tmp = None
                try:
                    stats["phase"] = "downloading_root_zip"
                    _persist_scan_progress(run_id, stats)

                    blob_client = container_client.get_blob_client(blob_name)
                    download_stream = blob_client.download_blob()
                    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
                    bytes_written = 0
                    for chunk in download_stream.chunks():
                        tmp.write(chunk)
                        bytes_written += len(chunk)
                        if bytes_written % (100 * 1024 * 1024) < len(chunk):
                            stats["download_mb"] = round(bytes_written / (1024 * 1024), 1)
                            _persist_scan_progress(run_id, stats)
                    tmp.close()
                    stats["download_mb"] = round(bytes_written / (1024 * 1024), 1)

                    stats["phase"] = "opening_root_zip"
                    _persist_scan_progress(run_id, stats)

                    with zipfile.ZipFile(tmp.name) as zf:
                        stats["zip_files_processed"] += 1
                        stats["files_processed"] += 1
                        entries = [e for e in zf.namelist() if not e.endswith("/")]
                        stats["zip_entries_total"] = len(entries)
                        stats["zip_entries_processed"] = 0
                        _persist_scan_progress(run_id, stats)

                        stats["phase"] = "extracting_entries"
                        for entry in entries:
                            parsed = _parse_attachment_path(entry)
                            if not parsed:
                                stats["skipped_no_match"] += 1
                                stats["zip_entries_processed"] += 1
                                continue
                            entry_job_id, entry_note_id, entry_filename = parsed
                            try:
                                entry_data = zf.read(entry)
                                _process_file(
                                    entry_data, entry_filename,
                                    entry_job_id, entry_note_id,
                                    blob_name + "/" + entry
                                )
                            except Exception:
                                stats["errors"] += 1
                            stats["zip_entries_processed"] += 1

                            if len(write_batch) >= 25:
                                _flush_batch()
                            if stats["zip_entries_processed"] % 200 == 0:
                                _persist_scan_progress(run_id, stats)

                    _flush_batch()
                except zipfile.BadZipFile:
                    stats["errors"] += 1
                except Exception as ze:
                    stats["errors"] += 1
                    stats["last_error"] = str(ze)[:300]
                finally:
                    if tmp is not None:
                        try:
                            os.unlink(tmp.name)
                        except OSError:
                            pass
                stats.pop("current_blob", None)
                stats.pop("download_mb", None)
                stats.pop("zip_entries_total", None)
                stats.pop("zip_entries_processed", None)
                _persist_scan_progress(run_id, stats)
                continue

            parsed = _parse_attachment_path(blob_name)
            if not parsed:
                stats["skipped_no_match"] += 1
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
        stats["status"] = "completed"

    except Exception as e:
        _flush_batch()
        stats["status"] = "failed"
        stats["error_message"] = str(e)[:500]

    _persist_scan_progress(run_id, stats)

    return stats


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
