import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import threading
import uuid
import zipfile
from datetime import datetime

try:
    import pytz
    _MELB_TZ = pytz.timezone("Australia/Melbourne")
except ImportError:
    _MELB_TZ = None


def _utc_to_melb(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if _MELB_TZ:
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            dt = dt.astimezone(_MELB_TZ)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except (ValueError, AttributeError):
        return None


_NOTE_DATE_RE = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})(\d{2,4})\s+(\d{1,2})[:\.](\d{2})\s*([AaPp][Mm])?(?:\s|$)"
)
_SLASH_DATE_RE = re.compile(
    r"^(\d{1,2})/(\d{1,2})/(\d{2,4})\s+at\s+(\d{1,2})[:\.](\d{2})\s*([AaPp][Mm])?(?:\s|$)",
    re.IGNORECASE,
)
_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _apply_ampm(hour, minute, ampm):
    h = int(hour)
    mi = int(minute)
    if ampm:
        ap = ampm.lower()
        if ap == "am" and h == 12:
            h = 0
        elif ap == "pm" and h != 12:
            h += 12
    return h, mi


def _parse_note_text_date(text):
    if not text:
        return None
    s = text.strip()
    m = _NOTE_DATE_RE.match(s)
    if m:
        day, mon_str, year_str, hour, minute, ampm = m.groups()
        mon = _MONTH_MAP.get(mon_str.lower())
        if not mon:
            return None
        year = int(year_str)
        if year < 100:
            year += 2000
        try:
            h, mi = _apply_ampm(hour, minute, ampm)
            dt = datetime(year, mon, int(day), h, mi)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except (ValueError, TypeError):
            return None

    m2 = _SLASH_DATE_RE.match(s)
    if m2:
        day, month, year_str, hour, minute, ampm = m2.groups()
        year = int(year_str)
        if year < 100:
            year += 2000
        try:
            h, mi = _apply_ampm(hour, minute, ampm)
            dt = datetime(year, int(month), int(day), h, mi)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except (ValueError, TypeError):
            return None

    return None

_ADMIN_AGENT_IGNORE = frozenset(s.lower() for s in (
    "Dom Powell", "Admin Office",
))

_ASSIGNED_RESOURCE_HEADERS = (
    "Assigned To", "Assigned Resource", "Resource", "Staff",
    "Assigned Staff", "Assigned User", "Technician",
)


def _detect_assigned_resource(csv_row):
    for h in _ASSIGNED_RESOURCE_HEADERS:
        val = (csv_row.get(h) or "").strip()
        if val:
            return val
    return ""


def _preserve_phone_text(val):
    """Restore leading zero on Australian phone numbers stripped by Excel/CSV numeric coercion.

    Rules:
      - Already starts with '+' or '0' → return as-is (correctly formatted)
      - Pure digits, 9 chars, starts with 2-9 → prepend '0' (e.g. 402801097 → 0402801097)
      - Pure digits, 11 chars, starts with '61' → prepend '+' (e.g. 61402801097 → +61402801097)
      - Contains any non-digit characters (spaces, dashes, parens) → return as-is
      - Otherwise → return as-is
    """
    if not val:
        return val
    s = str(val).strip()
    if not s:
        return s
    if s.startswith('+') or s.startswith('0'):
        return s
    digits = s.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
    if not digits.isdigit():
        return s
    if s != digits:
        return s
    if len(digits) == 9 and digits[0] in '23456789':
        return '0' + digits
    if len(digits) == 11 and digits.startswith('61'):
        return '+' + digits
    return s


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
        assigned_resource_raw TEXT,
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gsf_note_status ON geoop_staging_files(geoop_note_id, import_status)")

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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS geoop_source_client_map (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_name TEXT NOT NULL UNIQUE,
        canonical_name TEXT NOT NULL,
        client_id INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gscm_canonical ON geoop_source_client_map(canonical_name)")

    conn.commit()
    if close:
        conn.close()


_SOURCE_CANONICAL_MAP = {
    "allied": "Allied Finance",
    "allied finance": "Allied Finance",
    "allied  finance": "Allied Finance",
    "allied retail finance": "Allied Finance",
    "allied credit": "Allied Finance",
    "allied automotive finance": "Allied Finance",
    "allied dealer motor finance": "Allied Finance",
    "allied retail finance trading as dealer motor finance": "Allied Finance",
    "toyota": "Toyota Finance",
    "toyota finance": "Toyota Finance",
    "toyota finance australia": "Toyota Finance",
    "toyota loss recoveries": "Toyota Finance",
    "toyota austwide job.": "Toyota Finance",
    "pepper money": "Pepper Money",
    "pepper money limited": "Pepper Money",
    "pepper money limited:": "Pepper Money",
    "pepper auto finance": "Pepper Money",
    "pepper money:": "Pepper Money",
    "peppern": "Pepper Money",
    "vwfs": "VWFS",
    "volkswagen financial": "VWFS",
    "volkswagen financial service": "VWFS",
    "volkswagen financial service australia": "VWFS",
    "vw": "VWFS",
    "vw.": "VWFS",
    "vw finance.": "VWFS",
    "vw recoveries": "VWFS",
    "turo": "TURO",
    "turo reservation id": "TURO",
    "turo repo request": "TURO",
    "turo repo": "TURO",
    "trust & safety turo": "TURO",
    "urdrive": "TURO",
    "angle finance": "Angle Finance",
    "angle  finance": "Angle Finance",
    "angle": "Angle Finance",
    "capital finance": "Capital Finance",
    "capital  finance": "Capital Finance",
    "capital  finance": "Capital Finance",
    "capital": "Capital Finance",
    "macquarie leasing pty ltd": "Macquarie Leasing",
    "macquarie leasing": "Macquarie Leasing",
    "macquarie": "Macquarie Leasing",
    "macquarie leasing pty ltd: 001": "Macquarie Leasing",
    "macquarie leasing pty ltd 001": "Macquarie Leasing",
    "cba": "CBA",
    "commonwealth bank of australia": "CBA",
    "pickles": "Pickles",
    "pickles account": "Pickles",
    "pickles  account": "Pickles",
    "pickles auctions": "Pickles",
    "pickles auctions pty limited on behalf of capital finance on behalf of capital finance": "Pickles",
    "pickles auctions pty limited on behalf of westpac": "Pickles",
    "pickall": "Pickles",
    "boq": "BOQ",
    "boq equipment finance": "BOQ",
    "ncml": "NCML",
    "flexicommercial": "FlexiCommercial",
    "flexicommerical": "FlexiCommercial",
    "flexi commercial": "FlexiCommercial",
    "flexigroup": "FlexiCommercial",
    "moneyme": "MoneyMe",
    "money me": "MoneyMe",
    "harmoney": "Harmoney",
    "westpac": "Westpac",
    "westpac account": "Westpac",
    "st george": "St George",
    "st  george": "St George",
    "st george.": "St George",
    "stg": "St George",
    "collection house on behalf of st george": "St George",
    "collection house on behalf of st george bank limited": "St George",
    "bank of melbourne": "Bank of Melbourne",
    "bom": "Bank of Melbourne",
    "bankwest": "Bankwest",
    "bankwestsechl - bankwest - home loans": "Bankwest",
    "pioneer credit solutions pty ltd": "Pioneer Credit",
    "pioneer credit solutions": "Pioneer Credit",
    "pioneer credit": "Pioneer Credit",
    "mercedes": "Mercedes-Benz Finance",
    "mbfs": "Mercedes-Benz Finance",
    "swoosh": "Swoosh Finance",
    "swoosh finance": "Swoosh Finance",
    "nab": "NAB",
    "rapid loans": "Rapid Loans",
    "firstmac": "Firstmac",
    "powertorque finance": "PowerTorque Finance",
    "powertorque": "PowerTorque Finance",
    "power torque finance": "PowerTorque Finance",
    "bmw": "BMW Finance",
    "bmw chattel mortgage:": "BMW Finance",
    "bmw chattel mortgage": "BMW Finance",
    "bmw australia finance ltd": "BMW Finance",
    "yamaha motor finance": "Yamaha Motor Finance",
    "liberty": "Liberty Financial",
    "liberty file": "Liberty Financial",
    "liberty file 3886770 repo on sight": "Liberty Financial",
    "acm": "ACM",
    "now finance": "Now Finance",
    "now finance": "Now Finance",
    "credit corp group": "Credit Corp",
    "credit corp": "Credit Corp",
    "credit collection services group pty ltd": "Credit Corp",
    "latitude": "Latitude Financial",
    "ch ual": "Collection House",
    "collection house ual": "Collection House",
    "collection house on behalf of resimac": "Resimac",
    "resimac": "Resimac",
    "slattery auctions": "Slattery Auctions",
    "slatterys": "Slattery Auctions",
    "slatterys account": "Slattery Auctions",
    "slaterys": "Slattery Auctions",
    "slattery's": "Slattery Auctions",
    "slatmoney - slattery auctions - moneyme": "Slattery Auctions",
    "gla": "GLA",
    "australian motorcycle marine finance": "AMMF",
    "ammf": "AMMF",
    "jacaranda finance": "Jacaranda Finance",
    "jacaranda": "Jacaranda Finance",
    "shift": "Shift Finance",
    "shift financial": "Shift Finance",
    "shift finance australia": "Shift Finance",
    "difrent rental": "Difrent Rental",
    "finance one": "Finance One",
    "finance one commercial pty ltd": "Finance One",
    "finance  one": "Finance One",
    "finone": "Finance One",
    "finonecom": "Finance One",
    "1800 346 663 finance one commercial": "Finance One",
    "1800 346 663 finonecom": "Finance One",
    "1800 346 663  finance one commercial": "Finance One",
    "right road finance": "Right Road Finance",
    "automotive finance": "Automotive Finance",
    "moneytech": "Moneytech",
    "wise": "WISE Group",
    "wise group": "WISE Group",
    "polygon": "Polygon",
    "polygon group": "Polygon",
    "ausrn": "AUSRN",
    "aami": "AAMI",
    "raa": "RAA Insurance",
    "raa insurance": "RAA Insurance",
    "racv": "RACV",
    "flexfleet": "FlexFleet",
    "dealer motor finance australia": "Dealer Motor Finance",
    "scotpac": "ScotPac",
    "scottish pacific": "ScotPac",
    "scot pac": "ScotPac",
    "orix": "ORIX",
    "selfco": "Selfco Leasing",
    "selfco leasing": "Selfco Leasing",
    "plenti": "Plenti",
    "paccar financial": "Paccar Financial",
    "arg": "ARG",
    "scania finance": "Scania Finance",
    "scania finance australia pty ltd": "Scania Finance",
    "scania": "Scania Finance",
    "green light auto finance": "Greenlight Auto",
    "greenlight auto": "Greenlight Auto",
    "dll": "DLL",
    "azora": "Azora",
    "silverchef": "SilverChef",
    "silver chef": "SilverChef",
    "silver chef collections": "SilverChef",
    "multipli": "Multipli",
    "harley heaven finance": "Harley Heaven Finance",
    "smart selection rentals pty ltd": "Smart Selection Rentals",
    "truepillars": "TruePillars",
    "pfm mortgage": "PFM Mortgage",
    "metro finance": "Metro Finance",
    "leasewise": "Leasewise",
    "lease wise": "Leasewise",
    "c1 finance": "C1 Finance",
    "agl": "AGL",
    "sixt": "SIXT Rentals",
    "sixt rentals": "SIXT Rentals",
    "process serve": "Process Serve",
    "process serve": "Process Serve",
    "process serve": "Process Serve",
    "nci commercial collection": "NCI Commercial",
    "iron capital": "Iron Capital",
    "power alliance finance": "Power Alliance Finance",
    "fines victoria": "Fines Victoria",
    "kia finance": "Kia Finance",
    "mazda": "Mazda Finance",
    "legastream": "Legastream",
    "tg legal + technology on behalf of plenti finance": "Plenti",
    "axsesstoday": "Axsesstoday",
    "axsess": "Axsesstoday",
    "credit corp field calls": "Credit Corp",
    "bdo": "BDO",
}


def _normalise_source_name(raw):
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    key = s.lower().rstrip(".,;: ")
    key = re.sub(r'\s+', ' ', key)
    canonical = _SOURCE_CANONICAL_MAP.get(key)
    if canonical:
        return canonical
    for prefix, canon in sorted(_SOURCE_CANONICAL_MAP.items(), key=lambda x: -len(x[0])):
        if key.startswith(prefix + " ") or key.startswith(prefix + "/"):
            return canon
    _NOISE_PATTERNS = [
        r'^\d', r'^see ', r'^repo', r'^field', r'^collect', r'^audit',
        r'^upgraded', r'^upgrade', r'^complaint', r'^surveillance',
        r'^subpoena', r'^lockout', r'^investigation', r'^vacant',
        r'^serve ', r'^urgent', r'^sofp', r'^soc$', r'^no info',
        r'^ignore', r'^full debt', r'^\*', r'^#', r'^\+', r'^"',
        r'^co$', r'^\(', r'^2 of', r'^3 of', r'^1 of', r'^gtor',
    ]
    for pat in _NOISE_PATTERNS:
        if re.match(pat, key):
            return None
    if len(s) <= 3 and s.upper() not in ('CBA', 'NAB', 'BOQ', 'GLA', 'ACM', 'RAA', 'DLL', 'ARG', 'BDO', 'AGL'):
        return None
    return None


def populate_source_client_map(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ensure_staging_tables(conn)
    ts = _now()

    names = conn.execute("""
        SELECT parsed_client_name, COUNT(*) c
        FROM geoop_staging_jobs
        WHERE parsed_client_name IS NOT NULL AND parsed_client_name != ''
        GROUP BY parsed_client_name
        ORDER BY c DESC
    """).fetchall()

    canonical_counts = {}
    source_to_canonical = {}

    for row in names:
        raw = row["parsed_client_name"]
        canon = _normalise_source_name(raw)
        if canon:
            source_to_canonical[raw] = canon
            canonical_counts[canon] = canonical_counts.get(canon, 0) + row["c"]

    new_sources = 0

    for canon in sorted(canonical_counts.keys()):
        for raw_name, mapped_canon in source_to_canonical.items():
            if mapped_canon == canon:
                existing_map = conn.execute(
                    "SELECT id FROM geoop_source_client_map WHERE source_name = ?", (raw_name,)
                ).fetchone()
                if not existing_map:
                    conn.execute("""
                        INSERT INTO geoop_source_client_map (source_name, canonical_name, client_id, created_at)
                        VALUES (?, ?, NULL, ?)
                    """, (raw_name, canon, ts))
                    new_sources += 1
                else:
                    conn.execute("""
                        UPDATE geoop_source_client_map
                        SET canonical_name = ?, updated_at = ?
                        WHERE id = ?
                    """, (canon, ts, existing_map["id"]))

    conn.commit()
    if close:
        conn.close()

    return {
        "new_sources": new_sources,
        "canonical_groups": len(canonical_counts),
    }


def resolve_staging_client_ids(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ts = _now()

    source_map = {}
    rows = conn.execute("SELECT source_name, client_id FROM geoop_source_client_map WHERE client_id IS NOT NULL").fetchall()
    for r in rows:
        source_map[r["source_name"]] = r["client_id"]

    staged = conn.execute("""
        SELECT id, parsed_client_name FROM geoop_staging_jobs
        WHERE (axion_client_id IS NULL OR axion_client_id = 0)
        AND parsed_client_name IS NOT NULL AND parsed_client_name != ''
    """).fetchall()

    updated = 0
    for sj in staged:
        client_id = source_map.get(sj["parsed_client_name"])
        if client_id:
            conn.execute(
                "UPDATE geoop_staging_jobs SET axion_client_id = ? WHERE id = ?",
                (client_id, sj["id"])
            )
            updated += 1

    conn.commit()
    if close:
        conn.close()

    return {"updated": updated, "total_checked": len(staged)}


def backfill_job_client_ids(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ts = _now()

    updated = 0
    rows = conn.execute("""
        SELECT j.id AS job_id, sj.axion_client_id
        FROM jobs j
        JOIN geoop_staging_jobs sj ON CAST(sj.geoop_job_id AS TEXT) = j.geoop_job_id
        WHERE (j.client_id IS NULL OR j.client_id = 0)
        AND sj.axion_client_id IS NOT NULL AND sj.axion_client_id > 0
    """).fetchall()

    for r in rows:
        conn.execute(
            "UPDATE jobs SET client_id = ?, updated_at = ? WHERE id = ?",
            (r["axion_client_id"], ts, r["job_id"])
        )
        updated += 1

    conn.commit()
    if close:
        conn.close()

    return {"backfilled": updated}


def _parse_money(s):
    if not s:
        return 0
    s = s.replace(",", "").replace("$", "").replace(" ", "").strip()
    try:
        return round(float(s) * 100)
    except (ValueError, TypeError):
        return 0


def _normalise_au_date(raw):
    if not raw:
        return ""
    raw = raw.strip()
    parts = re.split(r'[/\-]', raw)
    if len(parts) != 3:
        return raw
    try:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        if year < 100:
            year = year + 2000 if year <= 69 else year + 1900
        from datetime import date as _date
        d = _date(year, month, day)
        return d.isoformat()
    except (ValueError, TypeError):
        return raw


def parse_description(desc):
    if not desc:
        return {}

    result = {}
    original = desc.strip()

    prefixes = []
    prefix_patterns = [
        r'\*+[^*]+\*+',
        r'(?:REPOSSESSION AUTHORITY|NO REPOSSESSION|DO NOT NEGOTIATE)[^.]*?(?:COMMENCES|SIGHTED)\s*',
        r'(?:REPOSSESSION AUTHORITY|NO REPOSSESSION|DO NOT NEGOTIATE)[^.]+\.\s*',
        r'PLEASE HAVE CUSTOMER CALL[^.]*?(?:ON SITE\.?\s*)',
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

    reg_match = re.search(r'(?<![A-Za-z])REG[:\s]+([A-Z0-9]{2,10}(?:\s*\([^)]*\))?)', clean, re.IGNORECASE)
    if reg_match:
        raw_reg = reg_match.group(1).strip()
        reg_clean = re.sub(r'\s*\([^)]*\)$', '', raw_reg).strip().upper()
        reg_clean = re.sub(r'VIN$', '', reg_clean, flags=re.IGNORECASE).strip()
        if len(reg_clean) >= 2:
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

    _date_sep = r'(?:on\s+(?:the\s+)?|Due\s+(?:F/?N\s+)?|Due\s+Date\s+)?'
    _nmpd_patterns = [
        r'(?:^|(?<=\s)|(?<=\d))N[MW]PD\s+\$?\s*\$?\s*([\d,]+\.?\d*)\s+' + _date_sep + r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
        r'(?:(?<![A-Za-z])|(?<=inc))NPD[:\s]+\$?\s*\$?\s*([\d,]+\.?\d*)\s+' + _date_sep + r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
        r'(?:^|(?<=\s)|(?<=\d))N[FW]PD\s+\$?\s*\$?\s*([\d,]+\.?\d*)\s+' + _date_sep + r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
        r'(?<![A-Za-z])(?:Due|PMT\s+Due)\s+(?:Date\s+)?(?:on\s+)?(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
    ]
    nmpd_match = None
    for _pat in _nmpd_patterns:
        all_matches = list(re.finditer(_pat, clean, re.IGNORECASE))
        if all_matches:
            nmpd_match = all_matches[-1]
            break
    if nmpd_match:
        groups = nmpd_match.groups()
        if len(groups) == 2:
            result["parsed_nmpd_amount_cents"] = _parse_money(groups[0])
            result["parsed_nmpd_date"] = _normalise_au_date(groups[1])
        elif len(groups) == 1:
            result["parsed_nmpd_date"] = _normalise_au_date(groups[0])

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

    _BAD_CLIENT_KW = ["security", "arrears", "regulated", "unregulated",
                       "please", "repossession", "authority", "field call",
                       "debt amount", "contract ", "writ and", "repo only",
                       "instructions", "see instructions", "client manager",
                       "deliver to", "note ", "must ", "call ","payout",
                       "turo res id", "res id"]

    def _valid_client(name):
        name = (name or "").strip().rstrip(" -")
        name = re.sub(r'\s*Repossessions?\b', '', name, flags=re.IGNORECASE).strip()
        if len(name) < 2 or len(name) > 100:
            return None
        if any(kw in name.lower() for kw in _BAD_CLIENT_KW):
            return None
        return name

    dual_account = re.search(
        r'(\w+)\s+account\s+:?\s*([\w\-/]+)\s*/\s*(\w.+?)\s+account\s+:?\s*([\w\-/]+)',
        clean, re.IGNORECASE
    )
    if dual_account:
        secondary = _valid_client(dual_account.group(3))
        primary = _valid_client(dual_account.group(1))
        if secondary:
            result["parsed_client_name"] = secondary
            result["parsed_account_number"] = dual_account.group(4).strip()
        elif primary:
            result["parsed_client_name"] = primary
            result["parsed_account_number"] = dual_account.group(2).strip()

    if "parsed_client_name" not in result:
        dual_slash = re.match(
            r'^(.+?)\s+((?=.*\d)[\w\-/]{3,})\s*/\s*(.+?)\s+((?=.*\d)[\w\-/]{3,})\s+(?:REGULATED|UNREGULATED|See\s)',
            clean, re.IGNORECASE
        )
        if dual_slash:
            primary = _valid_client(dual_slash.group(1))
            secondary = _valid_client(dual_slash.group(3))
            if primary:
                result["parsed_client_name"] = primary
                result["parsed_account_number"] = dual_slash.group(2).strip()
            elif secondary:
                result["parsed_client_name"] = secondary
                result["parsed_account_number"] = dual_slash.group(4).strip()

    if "parsed_client_name" not in result:
        slash_see = re.match(
            r'^(.+?)\s+(\d[\w\-/]{2,})\s+[Ss]ee\s',
            clean
        )
        if slash_see:
            client_name = _valid_client(slash_see.group(1))
            if client_name:
                result["parsed_client_name"] = client_name
                result["parsed_account_number"] = slash_see.group(2).strip()

    if "parsed_client_name" not in result:
        fc_upgrade = re.match(
            r'^[Ff]ield\s+[Cc]all(?:\s+[Uu]pgrade)?\s*-\s*([A-Z][\w\s]+?)(?:\s+(?:REGULATED|UNREGULATED)\b|\s+\d)',
            clean, re.IGNORECASE
        )
        if fc_upgrade:
            client_name = _valid_client(fc_upgrade.group(1))
            if client_name:
                result["parsed_client_name"] = client_name
        else:
            field_call = re.match(
                r'^(.+?)\s+[Ff]ield\s+[Cc]all\b',
                clean
            )
            if field_call:
                client_name = _valid_client(field_call.group(1))
                if client_name:
                    result["parsed_client_name"] = client_name

    if "parsed_client_name" not in result:
        dash_text_reg = re.match(
            r'^(.+?)\s*-\s*.+?\s+(?:Regulated|Unregulated)\b',
            clean, re.IGNORECASE
        )
        if dash_text_reg:
            client_name = _valid_client(dash_text_reg.group(1))
            if client_name:
                result["parsed_client_name"] = client_name

    if "parsed_client_name" not in result:
        client_patterns = [
            r'^(.+?)\s*-\s*([A-Za-z0-9][\w\-/]{2,})',
            r'^(.+?)\s+account\s+(\w[\w\-/]+)',
        ]
        for cp in client_patterns:
            cm = re.match(cp, clean, re.IGNORECASE)
            if cm:
                acct = cm.group(2).strip()
                client_name = _valid_client(cm.group(1))
                if client_name:
                    result["parsed_client_name"] = client_name
                    result["parsed_account_number"] = acct
                    break

    if "parsed_client_name" not in result:
        name_id_reg = re.match(
            r'^(.+?)\s+(\d[\w\-/]{2,})\s+(?:REGULATED|UNREGULATED|See\s)',
            clean, re.IGNORECASE
        )
        if name_id_reg:
            client_name = _valid_client(name_id_reg.group(1))
            if client_name:
                result["parsed_client_name"] = client_name
                result["parsed_account_number"] = name_id_reg.group(2).strip()

    if "parsed_client_name" not in result:
        name_then_type = re.match(
            r'^(.+?)\s+(?:Regulated|Unregulated)\b',
            clean, re.IGNORECASE
        )
        if name_then_type:
            raw = name_then_type.group(1).strip()
            parts = raw.rsplit(None, 1)
            if len(parts) == 2 and re.match(r'^(?=.*\d)[\w\-/]{3,}$', parts[1]):
                client_name = _valid_client(parts[0])
                if client_name:
                    result["parsed_client_name"] = client_name
                    result["parsed_account_number"] = parts[1]
            if "parsed_client_name" not in result:
                client_name = _valid_client(raw)
                if client_name:
                    result["parsed_client_name"] = client_name

    if "parsed_client_name" not in result:
        obo_parts = re.split(r'\bon behalf of\b', clean, flags=re.IGNORECASE)
        if len(obo_parts) >= 2:
            last = obo_parts[-1].strip()
            obo_dash = re.match(r'^(.+?)\s*-\s*([A-Za-z0-9][\w\-/]{2,})', last, re.IGNORECASE)
            if obo_dash:
                client_name = _valid_client(obo_dash.group(1))
                if client_name:
                    result["parsed_client_name"] = client_name
                    result["parsed_account_number"] = obo_dash.group(2).strip()
            else:
                obo_name = re.match(r'^(.+?)(?:\s+\d|\s*-\s*\$|\s+Regulated|\s+Unregulated|$)', last, re.IGNORECASE)
                if obo_name:
                    client_name = _valid_client(obo_name.group(1))
                    if client_name:
                        result["parsed_client_name"] = client_name

    if "parsed_client_name" not in result:
        dash_dollar = re.match(
            r'^(.+?)\s*-\s*\$',
            clean
        )
        if dash_dollar:
            client_name = _valid_client(dash_dollar.group(1))
            if client_name:
                result["parsed_client_name"] = client_name

    if "parsed_client_name" not in result:
        colon_prefix = re.match(
            r'^([A-Za-z][\w\s]+?):\s',
            clean
        )
        if colon_prefix:
            candidate = colon_prefix.group(1).strip()
            if len(candidate.split()) <= 4:
                client_name = _valid_client(candidate)
                if client_name:
                    result["parsed_client_name"] = client_name

    if "parsed_client_name" not in result:
        hash_pattern = re.match(
            r'^(.+?)\s+#\d',
            clean
        )
        if hash_pattern:
            client_name = _valid_client(hash_pattern.group(1))
            if client_name:
                result["parsed_client_name"] = client_name

    if "parsed_client_name" not in result:
        mid_dash_id = re.search(
            r'(?<!\w)([A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,5}?)\s*-\s*((?=.*\d)[A-Za-z0-9][\w\-/]{2,})\s+(?:Regulated|Unregulated)\b',
            clean
        )
        if mid_dash_id:
            client_name = _valid_client(mid_dash_id.group(1))
            if client_name:
                result["parsed_client_name"] = client_name
                result["parsed_account_number"] = mid_dash_id.group(2).strip()

    if "parsed_client_name" not in result:
        mid_name_id = re.search(
            r'(?<!\w)([A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,5}?)\s+((?=.*\d)[\w\-/]{3,})\s+(?:Regulated|Unregulated)\b',
            clean
        )
        if mid_name_id:
            client_name = _valid_client(mid_name_id.group(1))
            if client_name:
                result["parsed_client_name"] = client_name
                result["parsed_account_number"] = mid_name_id.group(2).strip()

    if "parsed_client_name" not in result:
        mid_name_type = re.search(
            r'(?<!\w)([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4})\s+(?:Regulated|Unregulated)\b',
            clean
        )
        if mid_name_type:
            client_name = _valid_client(mid_name_type.group(1))
            if client_name:
                result["parsed_client_name"] = client_name

    return result


def _normalise_client_name(name):
    if not name:
        return ""
    n = name.lower().strip()
    for suffix in [" pty ltd", " pty. ltd.", " pty. ltd",
                   " limited", " ltd", " ltd.", " inc", " inc.",
                   " finance", " leasing"]:
        if n.endswith(suffix):
            n = n[:-len(suffix)].strip()
    n = re.sub(r'[^a-z0-9\s]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


_client_cache = {}
_client_cache_ts = 0


def _get_client_list(conn):
    global _client_cache, _client_cache_ts
    import time
    now = time.time()
    if now - _client_cache_ts < 60 and _client_cache:
        return _client_cache
    all_clients = conn.execute("SELECT id, name FROM clients").fetchall()
    cache = {}
    for c in all_clients:
        cid = c["id"]
        raw = c["name"] or ""
        norm = _normalise_client_name(raw)
        cache[cid] = {"name": raw, "lower": raw.lower().strip(), "norm": norm}
    _client_cache = cache
    _client_cache_ts = now
    return cache


def _build_agent_resolver(conn):
    users = conn.execute("SELECT id, full_name FROM users").fetchall()
    user_by_name = {}
    user_by_lower = {}
    for u in users:
        fn = (u["full_name"] or "").strip()
        if fn:
            user_by_name[fn] = u["id"]
            user_by_lower[fn.lower()] = u["id"]

    aliases = conn.execute(
        "SELECT alias, canonical_name, user_id, ambiguous FROM agent_aliases WHERE active = 1"
    ).fetchall()
    alias_map = {}
    ambiguous_set = set()
    for a in aliases:
        key = (a["alias"] or "").strip().lower()
        if not key:
            continue
        if a["ambiguous"]:
            ambiguous_set.add(key)
        else:
            uid = a["user_id"]
            if not uid:
                canon = (a["canonical_name"] or "").strip()
                uid = user_by_lower.get(canon.lower())
            if uid:
                alias_map[key] = uid

    def resolve(raw_name):
        if not raw_name or not raw_name.strip():
            return None, None
        name = raw_name.strip()
        name_lower = name.lower()

        uid = user_by_lower.get(name_lower)
        if uid:
            return uid, None

        if name_lower in ambiguous_set:
            return None, "ambiguous"

        uid = alias_map.get(name_lower)
        if uid:
            return uid, None

        parts = name_lower.split()
        candidates = []
        for fn_lower, uid in user_by_lower.items():
            fn_parts = fn_lower.split()
            if len(parts) >= 1 and len(fn_parts) >= 1 and parts[0] == fn_parts[0]:
                if len(parts) == 1 and len(fn_parts) >= 2:
                    candidates.append(uid)
                elif len(parts) >= 2 and len(fn_parts) >= 2 and parts == fn_parts:
                    return uid, None
        if len(candidates) == 1:
            return candidates[0], None
        elif len(candidates) > 1:
            return None, "ambiguous"

        return None, "unmatched"

    return resolve


def seed_agent_aliases(conn):
    ts = _now()
    seeds = [
        ("GrantC",       "Grant Cook",    1, 0, "GeoOp login"),
        ("Grant Cook",   "Grant Cook",    1, 0, "GeoOp visits full name"),
        ("ChrisW",       "Chris Wintle",  4, 0, "GeoOp login"),
        ("Chris Wintle", "Chris Wintle",  4, 0, "GeoOp visits full name"),
        ("Chris W",      "Chris Wintle",  4, 0, "GeoOp login variant"),
        ("CraigW",       "Craig Wright",  8, 0, "GeoOp login"),
        ("Craig Wright", "Craig Wright",  8, 0, "GeoOp visits full name"),
        ("BPS",          "Craig Wright",  8, 0, "GeoOp initials"),
        ("JamesW",       "James Wintle",  5, 0, "GeoOp login"),
        ("James Wintle", "James Wintle",  5, 0, "GeoOp visits full name"),
        ("James W",      "James Wintle",  5, 0, "GeoOp login variant"),
        ("DanielC",      "Daniel C",      3, 0, "GeoOp login"),
        ("Daniel C",     "Daniel C",      3, 0, "GeoOp login variant"),
        ("CW",           "ambiguous",     None, 1, "Could be Chris Wintle or Craig Wright — requires manual review"),
    ]
    for alias, canon, uid, ambig, note in seeds:
        existing = conn.execute("SELECT id FROM agent_aliases WHERE alias = ? COLLATE NOCASE", (alias,)).fetchone()
        if not existing:
            conn.execute("""
                INSERT INTO agent_aliases (alias, canonical_name, user_id, active, ambiguous, notes, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?, ?, ?)
            """, (alias, canon, uid, ambig, note, ts, ts))
        elif uid is not None:
            conn.execute(
                "UPDATE agent_aliases SET user_id = ?, updated_at = ? WHERE id = ? AND user_id IS NULL",
                (uid, ts, existing["id"])
            )
    conn.commit()


def resolve_agent_for_import(conn, sj, resolver=None):
    if resolver is None:
        resolver = _build_agent_resolver(conn)

    raw_agent = ""
    try:
        raw_agent = (sj["assigned_resource_raw"] or "").strip()
    except (KeyError, IndexError):
        pass
    if not raw_agent:
        raw_agent = (sj["modified_by"] or sj["created_by"] or "").strip()
    if not raw_agent:
        return None, raw_agent, None

    if raw_agent.lower() in _ADMIN_AGENT_IGNORE:
        return None, None, "admin_ignored"

    user_id, status = resolver(raw_agent)
    return user_id, raw_agent, status


def stage_visits_csv(csv_path, conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ts = _now()
    resolver = _build_agent_resolver(conn)

    visit_map = {}
    total_rows = 0
    skipped_admin = 0

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            staff = (row.get("Staff Member") or "").strip()
            if not staff:
                continue
            if staff.lower() in _ADMIN_AGENT_IGNORE:
                skipped_admin += 1
                continue

            link = (row.get("Job Link") or "").strip()
            geoop_id = ""
            if "/jobs/" in link:
                geoop_id = link.rsplit("/jobs/", 1)[-1].strip().rstrip("/")
            ref_no = (row.get("Job Reference") or "").strip()

            booking_end = (row.get("Booking End Date") or row.get("Job End Date") or "").strip()

            key = geoop_id or ref_no
            if not key:
                continue

            existing = visit_map.get(key)
            if existing is None or booking_end > existing["date"]:
                visit_map[key] = {
                    "geoop_id": geoop_id,
                    "ref_no": ref_no,
                    "staff": staff,
                    "date": booking_end,
                }

    assigned = 0
    ambiguous_count = 0
    unmatched_job = 0
    unmatched_agent = 0

    for key, info in visit_map.items():
        geoop_id = info["geoop_id"]
        ref_no = info["ref_no"]
        staff = info["staff"]

        job = None
        if geoop_id:
            job = conn.execute(
                "SELECT id, assigned_user_id, status FROM jobs WHERE geoop_job_id = ?",
                (geoop_id,)
            ).fetchone()
        if not job and ref_no:
            job = conn.execute(
                "SELECT id, assigned_user_id, status FROM jobs WHERE display_ref = ? OR internal_job_number = ?",
                (ref_no, ref_no)
            ).fetchone()

        if not job:
            unmatched_job += 1
            continue

        if job["status"] in ("Completed", "Cancelled", "Invoiced", "Archived - Invoiced", "Cold Stored"):
            continue

        user_id, status = resolver(staff)
        if user_id:
            conn.execute(
                "UPDATE jobs SET assigned_user_id = ?, geoop_assigned_agent = ?, updated_at = ? WHERE id = ?",
                (user_id, staff, ts, job["id"])
            )
            assigned += 1
        elif status == "ambiguous":
            conn.execute(
                "UPDATE jobs SET geoop_assigned_agent = ?, assigned_user_id = NULL, updated_at = ? WHERE id = ?",
                (staff, ts, job["id"])
            )
            ambiguous_count += 1
        else:
            conn.execute(
                "UPDATE jobs SET geoop_assigned_agent = ?, updated_at = ? WHERE id = ?",
                (staff, ts, job["id"])
            )
            unmatched_agent += 1

    conn.commit()

    for key, info in visit_map.items():
        if info["geoop_id"]:
            conn.execute(
                "UPDATE geoop_staging_jobs SET assigned_resource_raw = ? WHERE geoop_job_id = ? AND (assigned_resource_raw IS NULL OR assigned_resource_raw = '')",
                (info["staff"], info["geoop_id"])
            )
    conn.commit()

    if close:
        conn.close()

    return {
        "total_visit_rows": total_rows,
        "unique_jobs_in_csv": len(visit_map),
        "assigned": assigned,
        "ambiguous": ambiguous_count,
        "unmatched_job": unmatched_job,
        "unmatched_agent": unmatched_agent,
        "skipped_admin": skipped_admin,
    }


def backfill_agent_assignments(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ts = _now()
    resolver = _build_agent_resolver(conn)

    conn.execute("""
        UPDATE jobs SET assigned_user_id = NULL, geoop_assigned_agent = NULL, updated_at = ?
        WHERE geoop_job_id IS NOT NULL
          AND geoop_assigned_agent IS NOT NULL
          AND LOWER(geoop_assigned_agent) IN ('dom powell', 'admin office')
          AND status NOT IN ('Completed', 'Cancelled', 'Invoiced', 'Archived - Invoiced', 'Cold Stored')
    """, (ts,))
    conn.commit()

    rows = conn.execute("""
        SELECT j.id, j.geoop_job_id, j.geoop_assigned_agent,
               sj.assigned_resource_raw, sj.created_by, sj.modified_by
        FROM jobs j
        JOIN geoop_staging_jobs sj ON CAST(sj.geoop_job_id AS TEXT) = j.geoop_job_id
        WHERE j.geoop_job_id IS NOT NULL
          AND j.status NOT IN ('Completed', 'Cancelled', 'Invoiced', 'Archived - Invoiced', 'Cold Stored')
    """).fetchall()

    assigned = 0
    ambiguous = 0
    unmatched = 0
    admin_ignored = 0
    skipped_empty = 0

    for r in rows:
        raw_agent = (r["assigned_resource_raw"] or "").strip()
        if not raw_agent:
            raw_agent = (r["modified_by"] or r["created_by"] or "").strip()
        if not raw_agent:
            skipped_empty += 1
            continue

        if raw_agent.lower() in _ADMIN_AGENT_IGNORE:
            if r["geoop_assigned_agent"] or False:
                conn.execute(
                    "UPDATE jobs SET geoop_assigned_agent = NULL, assigned_user_id = NULL, updated_at = ? WHERE id = ?",
                    (ts, r["id"])
                )
            admin_ignored += 1
            continue

        user_id, status = resolver(raw_agent)
        if user_id:
            conn.execute(
                "UPDATE jobs SET assigned_user_id = ?, geoop_assigned_agent = ?, updated_at = ? WHERE id = ?",
                (user_id, raw_agent, ts, r["id"])
            )
            assigned += 1
        elif status == "ambiguous":
            conn.execute(
                "UPDATE jobs SET geoop_assigned_agent = ?, assigned_user_id = NULL, updated_at = ? WHERE id = ?",
                (raw_agent, ts, r["id"])
            )
            ambiguous += 1
        else:
            conn.execute(
                "UPDATE jobs SET geoop_assigned_agent = ?, updated_at = ? WHERE id = ?",
                (raw_agent, ts, r["id"])
            )
            unmatched += 1

        if (assigned + ambiguous + unmatched + admin_ignored) % 500 == 0:
            conn.commit()

    conn.commit()
    if close:
        conn.close()

    return {
        "total_checked": len(rows),
        "assigned": assigned,
        "ambiguous": ambiguous,
        "unmatched": unmatched,
        "admin_ignored": admin_ignored,
        "skipped_empty": skipped_empty,
    }


def _match_client(conn, name):
    if not name or not name.strip():
        return None

    lookup = name.strip()
    lookup_lower = lookup.lower()

    clients = _get_client_list(conn)

    for cid, c in clients.items():
        if c["lower"] == lookup_lower:
            return cid

    norm = _normalise_client_name(name)
    if not norm:
        return None

    for cid, c in clients.items():
        if c["norm"] == norm:
            return cid

    norm_words = norm.split()
    if len(norm_words) >= 2:
        for cid, c in clients.items():
            c_words = c["norm"].split()
            if not c_words:
                continue
            overlap = set(norm_words) & set(c_words)
            if len(overlap) >= 2 and norm_words[0] in c_words:
                return cid

    return None


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
                _preserve_phone_text(row.get("Phone", "")),
                _preserve_phone_text(row.get("Mobile", "")),
                row.get("Created By", ""),
                row.get("Modified By", ""),
                _detect_assigned_resource(row),
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
                    created_by, modified_by, assigned_resource_raw,
                    date_created, date_modified, file_locations,
                    parsed_client_name, parsed_account_number, parsed_regulation_type,
                    parsed_amount_type, parsed_amount_cents, parsed_costs_cents,
                    parsed_nmpd_amount_cents, parsed_nmpd_date,
                    parsed_security_description, parsed_security_colour,
                    parsed_security_year, parsed_security_make, parsed_security_model,
                    parsed_reg, parsed_vin, parsed_deliver_to, parsed_notes,
                    created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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

    _source_map_cache = {}
    _scm_rows = conn.execute("SELECT source_name, client_id FROM geoop_source_client_map WHERE client_id IS NOT NULL").fetchall()
    for _scr in _scm_rows:
        _source_map_cache[_scr["source_name"]] = _scr["client_id"]

    _agent_resolver = _build_agent_resolver(conn)

    existing_rows = conn.execute(
        "SELECT id, internal_job_number, display_ref, client_job_number, geoop_job_id FROM jobs"
    ).fetchall()
    _existing_by_ijn = {}
    _existing_by_dr = {}
    _existing_by_dr_prefix = {}
    _existing_by_cjn = {}
    _existing_by_gid = {}
    for er in existing_rows:
        eid = er["id"]
        if er["internal_job_number"]:
            _existing_by_ijn[er["internal_job_number"]] = eid
        if er["display_ref"]:
            _existing_by_dr[er["display_ref"]] = eid
            base = er["display_ref"].split(" (")[0]
            _existing_by_dr_prefix[base] = eid
        if er["client_job_number"]:
            _existing_by_cjn[er["client_job_number"]] = eid
        if er["geoop_job_id"]:
            _existing_by_gid[er["geoop_job_id"].strip()] = eid

    def _find_existing(ref_no, geoop_id_str):
        if ref_no:
            eid = (_existing_by_ijn.get(ref_no)
                   or _existing_by_dr.get(ref_no)
                   or _existing_by_dr_prefix.get(ref_no))
            if eid:
                return eid
        if geoop_id_str:
            eid = (_existing_by_cjn.get(geoop_id_str)
                   or _existing_by_gid.get(geoop_id_str))
            if eid:
                return eid
        return None

    for sj in staged:
        geoop_id = sj["geoop_job_id"]

        ref_no = sj["reference_no"] or ""
        geoop_id_str = str(geoop_id).strip()
        existing_id = _find_existing(ref_no, geoop_id_str)

        if existing_id and mode == "insert_only":
            conn.execute(
                "UPDATE geoop_staging_jobs SET import_status='skipped_exists', axion_job_id=?, imported_at=? WHERE id=?",
                (existing_id, ts, sj["id"])
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

                mobile = _preserve_phone_text((sj["mobile"] or "").strip())
                phone = _preserve_phone_text((sj["phone"] or "").strip())
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

        client_id = sj["axion_client_id"]
        if not client_id:
            parsed_client = sj["parsed_client_name"] or ""
            if parsed_client:
                client_id = _source_map_cache.get(parsed_client)

        agent_user_id, raw_agent, _agent_status = resolve_agent_for_import(conn, sj, _agent_resolver)

        status = STATUS_MAP.get(sj["status_label"], "New")
        job_type = _determine_job_type(sj["job_title"])

        _nmpd_date = sj["parsed_nmpd_date"] or ""
        _pmt_freq = "Monthly" if _nmpd_date else ""

        if existing_id and mode == "update":
            conn.execute("""
                UPDATE jobs SET
                    status=?, job_address=?, description=?,
                    geoop_source_description=CASE WHEN (geoop_source_description IS NULL OR geoop_source_description='') THEN ? ELSE geoop_source_description END,
                    lender_name=?, account_number=?, regulation_type=?,
                    arrears_cents=?, costs_cents=?,
                    mmp_cents=?, job_due_date=?,
                    payment_frequency=COALESCE(NULLIF(payment_frequency,''), ?),
                    deliver_to=?, client_id=COALESCE(?, client_id),
                    geoop_job_id=COALESCE(geoop_job_id, ?),
                    assigned_user_id=COALESCE(?, assigned_user_id),
                    geoop_assigned_agent=COALESCE(?, geoop_assigned_agent),
                    updated_at=?
                WHERE id=?
            """, (
                status, full_address, sj["raw_description"],
                sj["raw_description"],
                sj["parsed_client_name"] or "", sj["parsed_account_number"] or "",
                sj["parsed_regulation_type"] or "",
                sj["parsed_amount_cents"] or 0, sj["parsed_costs_cents"] or 0,
                sj["parsed_nmpd_amount_cents"] or 0, _nmpd_date,
                _pmt_freq,
                sj["parsed_deliver_to"] or "", client_id,
                str(geoop_id).strip(),
                agent_user_id, raw_agent or None,
                ts,
                existing_id
            ))
            legacy_exists = conn.execute(
                "SELECT id FROM job_field_notes WHERE job_id=? AND note_type='geoop_import'",
                (existing_id,)
            ).fetchone()
            if not legacy_exists and sj["raw_description"]:
                conn.execute("""
                    INSERT INTO job_field_notes (job_id, created_by_user_id, note_text, note_type, created_at)
                    VALUES (?, 1, ?, 'geoop_import', ?)
                """, (existing_id, "[GeoOp Import] " + sj["raw_description"], ts))
            conn.execute(
                "UPDATE geoop_staging_jobs SET import_status='updated', axion_job_id=?, axion_client_id=?, imported_at=? WHERE id=?",
                (existing_id, client_id, ts, sj["id"])
            )
            updated += 1
            continue

        try:
            insert_ref = ref_no or str(geoop_id)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO jobs (
                    internal_job_number, display_ref, client_reference,
                    customer_id, client_id, job_type, visit_type, status, priority,
                    job_address, description, geoop_source_description,
                    lender_name, account_number, regulation_type,
                    arrears_cents, costs_cents, mmp_cents, job_due_date,
                    payment_frequency, deliver_to, client_job_number, geoop_job_id,
                    assigned_user_id, geoop_assigned_agent,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                insert_ref, insert_ref, sj["parsed_account_number"] or "",
                cust_id, client_id, job_type, "New Visit", status, "Normal",
                full_address, sj["raw_description"], sj["raw_description"],
                sj["parsed_client_name"] or "", sj["parsed_account_number"] or "",
                sj["parsed_regulation_type"] or "",
                sj["parsed_amount_cents"] or 0, sj["parsed_costs_cents"] or 0,
                sj["parsed_nmpd_amount_cents"] or 0, _nmpd_date,
                _pmt_freq, sj["parsed_deliver_to"] or "", geoop_id, str(geoop_id).strip(),
                agent_user_id, raw_agent or None,
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
                "UPDATE geoop_staging_jobs SET import_status='imported', axion_job_id=?, axion_customer_id=?, axion_client_id=?, imported_at=? WHERE id=?",
                (axion_job_id, cust_id, client_id, ts, sj["id"])
            )
            _existing_by_ijn[insert_ref] = axion_job_id
            _existing_by_dr[insert_ref] = axion_job_id
            _existing_by_dr_prefix[insert_ref.split(" (")[0]] = axion_job_id
            _existing_by_cjn[str(geoop_id)] = axion_job_id
            _existing_by_gid[geoop_id_str] = axion_job_id
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


def import_staged_jobs_range(ref_start, ref_end, conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    ts = _now()
    imported = 0
    skipped = 0
    errors = 0
    error_list = []

    staged = conn.execute("""
        SELECT * FROM geoop_staging_jobs
        WHERE import_status = 'pending'
          AND CAST(reference_no AS INTEGER) BETWEEN ? AND ?
        ORDER BY CAST(reference_no AS INTEGER)
    """, (ref_start, ref_end)).fetchall()

    if not staged:
        if close:
            conn.close()
        return {
            "imported": 0, "skipped": 0, "errors": 0,
            "error_details": [],
            "message": f"No pending staging rows found for references {ref_start}-{ref_end}",
        }

    _source_map_cache = {}
    _scm_rows = conn.execute("SELECT source_name, client_id FROM geoop_source_client_map WHERE client_id IS NOT NULL").fetchall()
    for _scr in _scm_rows:
        _source_map_cache[_scr["source_name"]] = _scr["client_id"]

    _agent_resolver = _build_agent_resolver(conn)

    existing_rows = conn.execute(
        "SELECT id, internal_job_number, display_ref, client_job_number, geoop_job_id FROM jobs"
    ).fetchall()
    _existing_by_ijn = {}
    _existing_by_dr = {}
    _existing_by_dr_prefix = {}
    _existing_by_cjn = {}
    _existing_by_gid = {}
    for er in existing_rows:
        eid = er["id"]
        if er["internal_job_number"]:
            _existing_by_ijn[er["internal_job_number"]] = eid
        if er["display_ref"]:
            _existing_by_dr[er["display_ref"]] = eid
            base = er["display_ref"].split(" (")[0]
            _existing_by_dr_prefix[base] = eid
        if er["client_job_number"]:
            _existing_by_cjn[er["client_job_number"]] = eid
        if er["geoop_job_id"]:
            _existing_by_gid[er["geoop_job_id"].strip()] = eid

    def _find_existing(ref_no, geoop_id_str):
        if ref_no:
            eid = (_existing_by_ijn.get(ref_no)
                   or _existing_by_dr.get(ref_no)
                   or _existing_by_dr_prefix.get(ref_no))
            if eid:
                return eid
        if geoop_id_str:
            eid = (_existing_by_cjn.get(geoop_id_str)
                   or _existing_by_gid.get(geoop_id_str))
            if eid:
                return eid
        return None

    for sj in staged:
        geoop_id = sj["geoop_job_id"]
        ref_no = sj["reference_no"] or ""
        geoop_id_str = str(geoop_id).strip()
        existing_id = _find_existing(ref_no, geoop_id_str)

        if existing_id:
            conn.execute(
                "UPDATE geoop_staging_jobs SET import_status='skipped_exists', axion_job_id=?, imported_at=? WHERE id=?",
                (existing_id, ts, sj["id"])
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
                mobile = _preserve_phone_text((sj["mobile"] or "").strip())
                phone = _preserve_phone_text((sj["phone"] or "").strip())
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

        client_id = sj["axion_client_id"]
        if not client_id:
            parsed_client = sj["parsed_client_name"] or ""
            if parsed_client:
                client_id = _source_map_cache.get(parsed_client)

        agent_user_id, raw_agent, _agent_status = resolve_agent_for_import(conn, sj, _agent_resolver)

        status = STATUS_MAP.get(sj["status_label"], "New")
        job_type = _determine_job_type(sj["job_title"])
        _nmpd_date = sj["parsed_nmpd_date"] or ""
        _pmt_freq = "Monthly" if _nmpd_date else ""

        try:
            insert_ref = ref_no or str(geoop_id)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO jobs (
                    internal_job_number, display_ref, client_reference,
                    customer_id, client_id, job_type, visit_type, status, priority,
                    job_address, description, geoop_source_description,
                    lender_name, account_number, regulation_type,
                    arrears_cents, costs_cents, mmp_cents, job_due_date,
                    payment_frequency, deliver_to, client_job_number, geoop_job_id,
                    assigned_user_id, geoop_assigned_agent,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                insert_ref, insert_ref, sj["parsed_account_number"] or "",
                cust_id, client_id, job_type, "New Visit", status, "Normal",
                full_address, sj["raw_description"], sj["raw_description"],
                sj["parsed_client_name"] or "", sj["parsed_account_number"] or "",
                sj["parsed_regulation_type"] or "",
                sj["parsed_amount_cents"] or 0, sj["parsed_costs_cents"] or 0,
                sj["parsed_nmpd_amount_cents"] or 0, _nmpd_date,
                _pmt_freq, sj["parsed_deliver_to"] or "", geoop_id, str(geoop_id).strip(),
                agent_user_id, raw_agent or None,
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
                "UPDATE geoop_staging_jobs SET import_status='imported', axion_job_id=?, axion_customer_id=?, axion_client_id=?, imported_at=? WHERE id=?",
                (axion_job_id, cust_id, client_id, ts, sj["id"])
            )
            _existing_by_ijn[insert_ref] = axion_job_id
            _existing_by_dr[insert_ref] = axion_job_id
            _existing_by_dr_prefix[insert_ref.split(" (")[0]] = axion_job_id
            _existing_by_cjn[str(geoop_id)] = axion_job_id
            _existing_by_gid[geoop_id_str] = axion_job_id
            imported += 1
        except Exception as e:
            conn.execute(
                "UPDATE geoop_staging_jobs SET import_status='error', error_message=?, imported_at=? WHERE id=?",
                (str(e)[:500], ts, sj["id"])
            )
            errors += 1
            error_list.append({"geoop_id": geoop_id, "ref": ref_no, "error": str(e)[:200]})

    conn.commit()
    if close:
        conn.close()

    return {
        "imported": imported,
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

    _bf_nmpd_date = parsed.get("parsed_nmpd_date", "") or ""
    _bf_pmt_freq = "Monthly" if _bf_nmpd_date else ""

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
            payment_frequency = CASE WHEN (payment_frequency IS NULL OR payment_frequency = '') THEN ? ELSE payment_frequency END,
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
        _bf_nmpd_date,
        _bf_pmt_freq,
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


def _resolve_stored_name(conn, geoop_note_id, original_filename):
    sf = conn.execute("""
        SELECT stored_filename FROM geoop_staging_files
        WHERE geoop_note_id = ? AND import_status = 'imported'
          AND stored_filename IS NOT NULL AND stored_filename != ''
          AND file_name = ?
        ORDER BY id DESC LIMIT 1
    """, (geoop_note_id, original_filename)).fetchone()
    if sf:
        return sf["stored_filename"]

    sf2 = conn.execute("""
        SELECT stored_filename FROM geoop_staging_files
        WHERE geoop_note_id = ? AND import_status = 'imported'
          AND stored_filename IS NOT NULL AND stored_filename != ''
        ORDER BY id DESC LIMIT 1
    """, (geoop_note_id,)).fetchone()
    if sf2:
        return sf2["stored_filename"]

    return None


def _ensure_job_note_file(conn, axion_note_id, staging_note, ts):
    file_name = (staging_note["file_name"] or "").strip()
    if not file_name or not axion_note_id:
        return

    stored = _resolve_stored_name(conn, staging_note["geoop_note_id"], file_name)

    if not stored:
        return

    try:
        conn.execute("""
            INSERT OR IGNORE INTO job_note_files (job_field_note_id, filename, filepath, uploaded_at)
            VALUES (?, ?, ?, ?)
        """, (axion_note_id, stored, stored, ts))
    except Exception:
        pass


def backfill_geoop_job_ids(conn=None):
    import logging as _log
    log = _log.getLogger("geoop_import")
    close = False
    if conn is None:
        conn = _db()
        close = True
    try:
        rows = conn.execute("""
            SELECT geoop_job_id, axion_job_id
            FROM geoop_staging_jobs
            WHERE axion_job_id IS NOT NULL AND geoop_job_id IS NOT NULL AND geoop_job_id != ''
        """).fetchall()
        updated = 0
        skipped = 0
        for r in rows:
            gid = str(r["geoop_job_id"]).strip()
            aid = r["axion_job_id"]
            if not gid:
                continue
            existing = conn.execute(
                "SELECT geoop_job_id FROM jobs WHERE id=?", (aid,)
            ).fetchone()
            if not existing:
                skipped += 1
                continue
            current = (existing["geoop_job_id"] or "").strip()
            if current == gid:
                skipped += 1
                continue
            if current:
                log.debug("Backfill geoop_job_ids: job %d already has geoop_job_id=%s, staging says %s — skipping", aid, current, gid)
                skipped += 1
                continue
            conn.execute("UPDATE jobs SET geoop_job_id=? WHERE id=?", (gid, aid))
            updated += 1
        conn.commit()
        log.info("Backfill geoop_job_ids: %d updated, %d skipped", updated, skipped)
        return {"updated": updated, "skipped": skipped}
    finally:
        if close:
            conn.close()


def _link_staged_attachments(conn):
    ts = _now()

    sf_map = {}
    try:
        sf_rows = conn.execute("""
            SELECT geoop_note_id, file_name, stored_filename
            FROM geoop_staging_files
            WHERE import_status = 'imported'
              AND stored_filename IS NOT NULL AND stored_filename != ''
            ORDER BY id DESC
        """).fetchall()
        for sr in sf_rows:
            key = (sr["geoop_note_id"], sr["file_name"])
            if key not in sf_map:
                sf_map[key] = sr["stored_filename"]
            fallback_key = (sr["geoop_note_id"], None)
            if fallback_key not in sf_map:
                sf_map[fallback_key] = sr["stored_filename"]
    except Exception:
        pass

    batch_size = 5000
    last_id = 0
    linked = 0

    while True:
        unlinked = conn.execute("""
            SELECT sn.id, sn.geoop_note_id, sn.file_name, sn.axion_note_id
            FROM geoop_staging_notes sn
            WHERE sn.id > ?
              AND sn.file_name IS NOT NULL AND sn.file_name != ''
              AND sn.axion_note_id IS NOT NULL
            ORDER BY sn.id
            LIMIT ?
        """, (last_id, batch_size)).fetchall()

        if not unlinked:
            break

        for row in unlinked:
            last_id = row["id"]

            stored = sf_map.get(
                (row["geoop_note_id"], row["file_name"]),
                sf_map.get(
                    (row["geoop_note_id"], None),
                    None
                )
            )

            if not stored:
                continue

            try:
                cur = conn.execute("""
                    INSERT OR IGNORE INTO job_note_files (job_field_note_id, filename, filepath, uploaded_at)
                    VALUES (?, ?, ?, ?)
                """, (row["axion_note_id"], stored, stored, ts))
                if cur.rowcount > 0:
                    linked += 1
            except Exception:
                pass

        conn.commit()

    conn.commit()
    return linked


def _reconcile_linked_to_parent(conn):
    unresolved = conn.execute("""
        SELECT id, files_location FROM geoop_staging_notes
        WHERE import_status = 'linked_to_parent' AND axion_note_id IS NULL
          AND files_location IS NOT NULL AND files_location != ''
    """).fetchall()
    for row in unresolved:
        loc_parts = (row["files_location"] or "").strip().strip("/").split("/")
        if len(loc_parts) < 3:
            continue
        parent_id = loc_parts[2]
        parent = conn.execute(
            "SELECT axion_note_id, axion_job_id FROM geoop_staging_notes WHERE geoop_note_id=? AND axion_note_id IS NOT NULL",
            (parent_id,)
        ).fetchone()
        if parent:
            conn.execute(
                "UPDATE geoop_staging_notes SET axion_note_id=?, axion_job_id=? WHERE id=?",
                (parent["axion_note_id"], parent["axion_job_id"], row["id"])
            )
    conn.commit()


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
    job_date_map = {}
    rows = conn.execute("""
        SELECT geoop_job_id, axion_job_id, date_modified, date_created
        FROM geoop_staging_jobs WHERE axion_job_id IS NOT NULL
    """).fetchall()
    for r in rows:
        job_map[r["geoop_job_id"]] = r["axion_job_id"]
        job_date_map[r["geoop_job_id"]] = r["date_modified"] or r["date_created"] or ""

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
            has_file = bool((note["file_name"] or "").strip())
            if not note_text and not has_file:
                conn.execute(
                    "UPDATE geoop_staging_notes SET import_status='skipped_empty', imported_at=? WHERE id=?",
                    (ts, note["id"])
                )
                skipped += 1
                continue

            if has_file and not note_text:
                files_loc = (note["files_location"] or "").strip().strip("/")
                loc_parts = files_loc.split("/")
                if len(loc_parts) >= 3 and loc_parts[2] != note["geoop_note_id"]:
                    parent_id = loc_parts[2]
                    parent = conn.execute(
                        "SELECT axion_note_id FROM geoop_staging_notes WHERE geoop_note_id=?",
                        (parent_id,)
                    ).fetchone()
                    parent_axion_id = parent["axion_note_id"] if parent else None
                    conn.execute(
                        "UPDATE geoop_staging_notes SET import_status='linked_to_parent', axion_job_id=?, axion_note_id=?, imported_at=? WHERE id=?",
                        (axion_job_id, parent_axion_id, ts, note["id"])
                    )
                    skipped += 1
                    continue
                note_text = "[Attachment: " + (note["file_name"] or "file") + "]"

            raw_date = note["file_date"] or ""
            note_date = None
            if raw_date:
                note_date = _utc_to_melb(raw_date)
            if not note_date:
                note_date = _parse_note_text_date(note_text)
            if not note_date:
                fallback = job_date_map.get(note["geoop_job_id"], "")
                if fallback:
                    note_date = _utc_to_melb(fallback)
            if not note_date:
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

                if has_file:
                    _ensure_job_note_file(conn, note_id, note, ts)
            except Exception as e:
                conn.execute(
                    "UPDATE geoop_staging_notes SET import_status='error', error_message=?, imported_at=? WHERE id=?",
                    (str(e)[:500], ts, note["id"])
                )
                errors += 1

        conn.commit()

    conn.commit()

    _reconcile_linked_to_parent(conn)
    _link_staged_attachments(conn)

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
            parts = [p for p in parts if p]
            if len(parts) < 4:
                return None
            att_idx = None
            for i, p in enumerate(parts):
                if p == "attachments":
                    att_idx = i
                    break
            if att_idx is not None and len(parts) >= att_idx + 4:
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
            if len(parts) >= 4 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                geoop_job_id = parts[1]
                geoop_note_id = parts[2]
                filename = parts[-1]
                if not filename:
                    return None
                return geoop_job_id, geoop_note_id, filename
            return None

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


_file_recovery_lock = threading.Lock()
_file_recovery_progress = {"status": "idle"}


def get_file_recovery_progress():
    return dict(_file_recovery_progress)


def _parse_zip_entry_path(path_str):
    parts = path_str.replace("\\", "/").split("/")
    parts = [p for p in parts if p]
    if len(parts) < 4:
        return None
    att_idx = None
    for i, p in enumerate(parts):
        if p == "attachments":
            att_idx = i
            break
    if att_idx is not None and len(parts) >= att_idx + 5:
        account_id = parts[att_idx + 1].strip()
        geoop_job_id = parts[att_idx + 2].strip()
        geoop_note_id = parts[att_idx + 3].strip()
        if not geoop_job_id or not geoop_note_id:
            return None
        raw_filename = parts[-1]
        if not raw_filename:
            return None
        return geoop_job_id, geoop_note_id, raw_filename
    if att_idx is not None and len(parts) >= att_idx + 4:
        geoop_job_id = parts[att_idx + 1].strip()
        geoop_note_id = parts[att_idx + 2].strip()
        if not geoop_job_id or not geoop_note_id:
            return None
        raw_filename = parts[-1]
        if not raw_filename:
            return None
        return geoop_job_id, geoop_note_id, raw_filename
    if len(parts) >= 4 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
        geoop_job_id = parts[1].strip()
        geoop_note_id = parts[2].strip()
        filename = parts[-1]
        if not filename:
            return None
        return geoop_job_id, geoop_note_id, filename
    return None


def recover_files_from_zips(zip_paths, upload_dir=None):
    if not _file_recovery_lock.acquire(blocking=False):
        return False
    _file_recovery_progress.clear()
    _file_recovery_progress.update({
        "status": "running",
        "zips_total": len(zip_paths),
        "zips_processed": 0,
        "entries_scanned": 0,
        "files_restored": 0,
        "already_present": 0,
        "no_db_mapping": 0,
        "direct_linked": 0,
        "skipped_no_match": 0,
        "parse_failed": 0,
        "errors": 0,
        "current_zip": "",
        "unmatched_diagnostics": [],
    })
    target_dir = upload_dir or UPLOAD_FOLDER

    def _run():
        import logging
        log = logging.getLogger("geoop_import")
        try:
            conn = _db()
            try:
                sf_map = {}
                sf_note_counts = {}
                for r in conn.execute("""
                    SELECT geoop_note_id, file_name, stored_filename
                    FROM geoop_staging_files
                    WHERE stored_filename IS NOT NULL AND stored_filename != ''
                      AND import_status = 'imported'
                    ORDER BY id DESC
                """).fetchall():
                    key = (str(r["geoop_note_id"]).strip(), r["file_name"])
                    if key not in sf_map:
                        sf_map[key] = r["stored_filename"]
                    nid = str(r["geoop_note_id"]).strip()
                    sf_note_counts[nid] = sf_note_counts.get(nid, 0) + 1
                    if sf_note_counts[nid] == 1:
                        sf_map[(nid, None)] = r["stored_filename"]
                    else:
                        sf_map.pop((nid, None), None)

                geoop_job_map = {}
                for r in conn.execute("""
                    SELECT id, geoop_job_id FROM jobs
                    WHERE geoop_job_id IS NOT NULL AND geoop_job_id != ''
                """).fetchall():
                    geoop_job_map[str(r["geoop_job_id"]).strip()] = r["id"]

            finally:
                conn.close()

            log.info("File recovery: %d staging file mappings, %d job ID mappings, %d ZIPs to process",
                     len(sf_map), len(geoop_job_map), len(zip_paths))

            os.makedirs(target_dir, exist_ok=True)

            for zip_path in zip_paths:
                zip_basename = os.path.basename(zip_path)
                _file_recovery_progress["current_zip"] = zip_basename
                log.info("File recovery: processing %s", zip_basename)

                try:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        entries = [e for e in zf.namelist() if not e.endswith("/")]
                        for entry in entries:
                            _file_recovery_progress["entries_scanned"] += 1

                            parsed = _parse_zip_entry_path(entry)
                            if not parsed:
                                _file_recovery_progress["parse_failed"] += 1
                                continue

                            geoop_job_id, geoop_note_id, entry_filename = parsed
                            geoop_job_id = str(geoop_job_id).strip()
                            geoop_note_id = str(geoop_note_id).strip()

                            stored_name = sf_map.get((geoop_note_id, entry_filename))
                            if not stored_name:
                                underscore_idx = entry_filename.find("_")
                                stripped_name = entry_filename[underscore_idx + 1:] if underscore_idx > 0 else None
                                if stripped_name:
                                    stored_name = sf_map.get((geoop_note_id, stripped_name))
                            if not stored_name:
                                stored_name = sf_map.get((geoop_note_id, None))

                            if stored_name:
                                safe_name = os.path.basename(stored_name)
                                if not safe_name or safe_name != stored_name:
                                    _file_recovery_progress["errors"] += 1
                                    continue
                                dest_path = os.path.join(target_dir, safe_name)
                                abs_dest = os.path.abspath(dest_path)
                                abs_target = os.path.abspath(target_dir)
                                if not abs_dest.startswith(abs_target + os.sep):
                                    _file_recovery_progress["errors"] += 1
                                    continue
                                if os.path.exists(dest_path):
                                    _file_recovery_progress["already_present"] += 1
                                    continue

                                try:
                                    data = zf.read(entry)
                                    with open(dest_path, "wb") as fh:
                                        fh.write(data)
                                    _file_recovery_progress["files_restored"] += 1
                                except Exception as ex:
                                    _file_recovery_progress["errors"] += 1
                                    log.warning("File recovery: error extracting %s: %s", entry, str(ex)[:200])
                            else:
                                axion_job_id = geoop_job_map.get(geoop_job_id)
                                if not axion_job_id:
                                    _file_recovery_progress["skipped_no_match"] += 1
                                    diag = _file_recovery_progress["unmatched_diagnostics"]
                                    if len(diag) < 200:
                                        diag.append({"geoop_job_id": geoop_job_id, "filename": entry_filename})
                                    log.debug("File recovery: no job match for geoop_job_id=%s file=%s", geoop_job_id, entry_filename)
                                    continue

                                safe_base = re.sub(r'[^\w.\-]', '_', entry_filename)
                                safe_stored = "geoop_{}_{}".format(geoop_job_id, safe_base)
                                orig_safe = os.path.basename(entry_filename)
                                orig_path = os.path.join(target_dir, orig_safe) if orig_safe else None
                                dest_path = os.path.join(target_dir, safe_stored)
                                abs_dest = os.path.abspath(dest_path)
                                abs_target = os.path.abspath(target_dir)
                                if not abs_dest.startswith(abs_target + os.sep):
                                    _file_recovery_progress["errors"] += 1
                                    continue
                                already_orig = orig_path and os.path.exists(orig_path)
                                already_safe = os.path.exists(dest_path)
                                if already_orig and already_safe:
                                    _file_recovery_progress["already_present"] += 1
                                    continue

                                try:
                                    data = zf.read(entry)
                                    if not already_safe:
                                        with open(dest_path, "wb") as fh:
                                            fh.write(data)
                                    if orig_path and not already_orig and orig_safe != safe_stored:
                                        abs_orig = os.path.abspath(orig_path)
                                        if abs_orig.startswith(os.path.abspath(target_dir) + os.sep):
                                            with open(orig_path, "wb") as fh2:
                                                fh2.write(data)

                                    dconn = _db()
                                    try:
                                        orphan = dconn.execute(
                                            "SELECT jnf.id, jnf.filename, jnf.filepath FROM job_note_files jnf "
                                            "JOIN job_field_notes jfn ON jfn.id = jnf.job_field_note_id "
                                            "WHERE jfn.job_id=? AND (jnf.filename=? OR jnf.filepath=? OR jnf.filename=? OR jnf.filepath=?)",
                                            (axion_job_id, entry_filename, entry_filename, safe_stored, safe_stored)
                                        ).fetchone()
                                        if orphan:
                                            dconn.execute(
                                                "UPDATE job_note_files SET filepath=?, uploaded_at=? WHERE id=?",
                                                (safe_stored, _now(), orphan["id"])
                                            )
                                        else:
                                            note = dconn.execute(
                                                "SELECT id FROM job_field_notes WHERE job_id=? AND note_type='geoop_import' LIMIT 1",
                                                (axion_job_id,)
                                            ).fetchone()
                                            if note:
                                                dconn.execute("""
                                                    INSERT OR IGNORE INTO job_note_files (job_field_note_id, filename, filepath, uploaded_at)
                                                    VALUES (?, ?, ?, ?)
                                                """, (note["id"], entry_filename, safe_stored, _now()))
                                            else:
                                                cur2 = dconn.cursor()
                                                cur2.execute("""
                                                    INSERT INTO job_field_notes (job_id, created_by_user_id, note_text, note_type, created_at)
                                                    VALUES (?, 1, ?, 'geoop_import', ?)
                                                """, (axion_job_id, "[GeoOp Attachment Recovery]", _now()))
                                                new_note_id = cur2.lastrowid
                                                dconn.execute("""
                                                    INSERT OR IGNORE INTO job_note_files (job_field_note_id, filename, filepath, uploaded_at)
                                                    VALUES (?, ?, ?, ?)
                                                """, (new_note_id, entry_filename, safe_stored, _now()))
                                        dconn.commit()
                                    finally:
                                        dconn.close()

                                    _file_recovery_progress["direct_linked"] += 1
                                    log.info("File recovery: direct-linked %s -> job %d as %s", entry_filename, axion_job_id, safe_stored)
                                except Exception as ex:
                                    _file_recovery_progress["errors"] += 1
                                    log.warning("File recovery: error extracting/linking %s: %s", entry, str(ex)[:200])

                            if _file_recovery_progress["entries_scanned"] % 500 == 0:
                                log.info("File recovery: scanned %d entries, restored %d, direct-linked %d",
                                         _file_recovery_progress["entries_scanned"],
                                         _file_recovery_progress["files_restored"],
                                         _file_recovery_progress["direct_linked"])

                except zipfile.BadZipFile as bze:
                    _file_recovery_progress["errors"] += 1
                    log.error("File recovery: bad ZIP %s: %s", zip_basename, str(bze)[:200])
                except Exception as ze:
                    _file_recovery_progress["errors"] += 1
                    log.error("File recovery: error processing %s: %s", zip_basename, str(ze)[:300])

                _file_recovery_progress["zips_processed"] += 1

            _file_recovery_progress["status"] = "complete"
            _file_recovery_progress["current_zip"] = ""
            log.info("File recovery complete: %d restored (staging), %d direct-linked (job ID), %d already present, %d no match, %d no mapping, %d errors",
                     _file_recovery_progress["files_restored"],
                     _file_recovery_progress["direct_linked"],
                     _file_recovery_progress["already_present"],
                     _file_recovery_progress["skipped_no_match"],
                     _file_recovery_progress["no_db_mapping"],
                     _file_recovery_progress["errors"])
        except Exception as e:
            log.error("File recovery failed: %s", e)
            _file_recovery_progress.update({"status": "error", "error": str(e)[:500]})
        finally:
            _file_recovery_lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return True


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


_CLIENT_BACKFILL_BATCH = 250


def backfill_client_links(run_id=None):
    ts = _now()
    stats = {
        "status": "running",
        "total_eligible": 0,
        "jobs_processed": 0,
        "matched": 0,
        "already_set": 0,
        "no_source": 0,
        "no_match": 0,
        "errors": 0,
        "batch_number": 0,
        "last_job_id": 0,
    }

    try:
        conn = _db()
        total = conn.execute("""
            SELECT COUNT(*) FROM jobs
            WHERE client_job_number IS NOT NULL AND client_job_number != ''
              AND (client_id IS NULL OR client_id = 0)
        """).fetchone()[0]
        stats["total_eligible"] = total

        already_set = conn.execute("""
            SELECT COUNT(*) FROM jobs
            WHERE client_job_number IS NOT NULL AND client_job_number != ''
              AND client_id IS NOT NULL AND client_id > 0
        """).fetchone()[0]
        stats["already_set"] = already_set
        conn.close()

        if run_id:
            _persist_client_backfill_progress(run_id, stats)

        last_id = 0
        while True:
            conn = _db()
            batch = conn.execute("""
                SELECT j.id, j.lender_name, j.description,
                       j.geoop_source_description, j.client_id
                FROM jobs j
                WHERE j.client_job_number IS NOT NULL AND j.client_job_number != ''
                  AND (j.client_id IS NULL OR j.client_id = 0)
                  AND j.id > ?
                ORDER BY j.id
                LIMIT ?
            """, (last_id, _CLIENT_BACKFILL_BATCH)).fetchall()

            if not batch:
                conn.close()
                break

            stats["batch_number"] += 1

            if stats["batch_number"] == 1:
                _scm_rows = conn.execute("SELECT source_name, client_id FROM geoop_source_client_map WHERE client_id IS NOT NULL").fetchall()
                backfill_client_links._scm = {r["source_name"]: r["client_id"] for r in _scm_rows}
            _scm = backfill_client_links._scm

            for row in batch:
                stats["jobs_processed"] += 1
                last_id = row["id"]
                stats["last_job_id"] = last_id

                try:
                    client_id = None
                    source_name = None

                    if row["lender_name"]:
                        source_name = row["lender_name"]
                        client_id = _scm.get(source_name)

                    if not client_id:
                        raw_desc = row["geoop_source_description"] or row["description"] or ""
                        if raw_desc:
                            parsed = parse_description(raw_desc)
                            pn = parsed.get("parsed_client_name")
                            if pn:
                                source_name = pn
                                client_id = _scm.get(pn)

                    if client_id:
                        conn.execute(
                            "UPDATE jobs SET client_id=?, updated_at=? WHERE id=?",
                            (client_id, ts, row["id"])
                        )
                        if source_name and not row["lender_name"]:
                            conn.execute(
                                "UPDATE jobs SET lender_name=? WHERE id=? AND (lender_name IS NULL OR lender_name='')",
                                (source_name, row["id"])
                            )
                        stats["matched"] += 1
                    elif not source_name:
                        stats["no_source"] += 1
                    else:
                        stats["no_match"] += 1

                except Exception as e:
                    stats["errors"] += 1

            conn.commit()
            conn.close()

            if run_id:
                _persist_client_backfill_progress(run_id, stats)

        stats["status"] = "completed"
    except Exception as e:
        stats["status"] = "failed"
        stats["error_message"] = str(e)[:500]

    if run_id:
        _persist_client_backfill_progress(run_id, stats)

    return stats


def _persist_client_backfill_progress(run_id, stats):
    try:
        import json as _json
        conn = _db()
        conn.execute("""
            UPDATE geoop_import_runs
            SET diagnostics_json = ?, completed_at = CASE WHEN ? IN ('completed','failed') THEN ? ELSE completed_at END,
                status = ?
            WHERE id = ?
        """, (
            _json.dumps(stats),
            stats["status"], _now(),
            stats["status"] if stats["status"] in ("completed", "failed") else "running",
            run_id
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_client_gap_report(conn=None):
    close = False
    if conn is None:
        conn = _db()
        close = True

    rows = conn.execute("""
        SELECT j.id, j.internal_job_number, j.client_job_number,
               j.lender_name, j.description, j.geoop_source_description,
               j.client_id, j.status,
               sj.geoop_job_id, sj.company, sj.parsed_client_name,
               sj.raw_description AS staging_description
        FROM jobs j
        LEFT JOIN geoop_staging_jobs sj ON sj.axion_job_id = j.id
        WHERE j.client_job_number IS NOT NULL AND j.client_job_number != ''
          AND (j.client_id IS NULL OR j.client_id = 0)
        ORDER BY j.id
    """).fetchall()

    report = []
    for r in rows:
        raw_desc = r["geoop_source_description"] or r["description"] or ""
        parsed = parse_description(raw_desc) if raw_desc else {}
        parsed_name = parsed.get("parsed_client_name", "")

        if not raw_desc:
            reason = "no_source_data"
        elif not parsed_name and not r["lender_name"]:
            reason = "parse_failed"
        elif parsed_name or r["lender_name"]:
            reason = "no_client_match"
        else:
            reason = "unknown"

        report.append({
            "job_id": r["id"],
            "internal_job_number": r["internal_job_number"] or "",
            "geoop_job_id": r["geoop_job_id"] or r["client_job_number"] or "",
            "status": r["status"] or "",
            "lender_name": r["lender_name"] or "",
            "parsed_client_name": parsed_name,
            "company": r["company"] or "",
            "description_snippet": (raw_desc[:200] if raw_desc else ""),
            "reason": reason,
        })

    summary = {
        "total_gaps": len(report),
        "no_source_data": sum(1 for r in report if r["reason"] == "no_source_data"),
        "parse_failed": sum(1 for r in report if r["reason"] == "parse_failed"),
        "no_client_match": sum(1 for r in report if r["reason"] == "no_client_match"),
    }

    if close:
        conn.close()

    return {"summary": summary, "rows": report}


_audit_cache = {"result": None, "generated_at": None, "status": "idle", "error": None}
_audit_lock = threading.Lock()
_audit_cache_lock = threading.Lock()


def get_attachment_audit_cached():
    with _audit_cache_lock:
        return {
            "result": _audit_cache["result"],
            "generated_at": _audit_cache["generated_at"],
            "status": _audit_cache["status"],
            "error": _audit_cache["error"],
        }


def start_attachment_audit_background():
    if not _audit_lock.acquire(blocking=False):
        return False
    with _audit_cache_lock:
        _audit_cache["status"] = "running"
        _audit_cache["error"] = None

    def _run():
        import logging
        log = logging.getLogger("geoop_import")
        try:
            log.info("Attachment audit background thread started")
            conn = _db()
            try:
                result = _compute_attachment_audit(conn)
                with _audit_cache_lock:
                    _audit_cache["result"] = result
                    _audit_cache["generated_at"] = _now()
                    _audit_cache["status"] = "complete"
                    _audit_cache["error"] = None
                log.info("Attachment audit completed successfully")
            finally:
                conn.close()
        except Exception as e:
            log.error("Attachment audit failed: %s", e)
            with _audit_cache_lock:
                _audit_cache["status"] = "error"
                _audit_cache["error"] = str(e)[:500]
        finally:
            _audit_lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return True


def _compute_attachment_audit(conn):
    result = {}

    total_notes = conn.execute("SELECT COUNT(*) FROM geoop_staging_notes").fetchone()[0]
    result["total_staging_notes"] = total_notes

    by_status = conn.execute(
        "SELECT import_status, COUNT(*) c FROM geoop_staging_notes GROUP BY import_status ORDER BY c DESC"
    ).fetchall()
    result["notes_by_status"] = {r[0]: r[1] for r in by_status}

    with_files = conn.execute(
        "SELECT COUNT(*) FROM geoop_staging_notes WHERE file_name IS NOT NULL AND file_name != ''"
    ).fetchone()[0]
    result["notes_with_file_references"] = with_files

    files_linked = conn.execute(
        "SELECT COUNT(*) FROM geoop_staging_notes WHERE file_name IS NOT NULL AND file_name != '' AND axion_note_id IS NOT NULL"
    ).fetchone()[0]
    result["files_linked_to_notes"] = files_linked
    result["files_unlinked"] = with_files - files_linked

    files_no_text = conn.execute("""
        SELECT COUNT(*) FROM geoop_staging_notes
        WHERE (file_name IS NOT NULL AND file_name != '')
          AND (note_description IS NULL OR note_description = '' OR TRIM(note_description) = '')
    """).fetchone()[0]
    result["files_with_no_text"] = files_no_text

    linked_to_parent = conn.execute(
        "SELECT COUNT(*) FROM geoop_staging_notes WHERE import_status = 'linked_to_parent'"
    ).fetchone()[0]
    result["multi_file_children_resolved"] = linked_to_parent

    linked_to_parent_pending = conn.execute(
        "SELECT COUNT(*) FROM geoop_staging_notes WHERE import_status = 'linked_to_parent' AND axion_note_id IS NULL"
    ).fetchone()[0]
    result["multi_file_children_awaiting_parent_import"] = linked_to_parent_pending

    mapped_no_jnf = conn.execute("""
        SELECT COUNT(*) FROM geoop_staging_notes sn
        WHERE sn.file_name IS NOT NULL AND sn.file_name != ''
          AND sn.axion_note_id IS NOT NULL
          AND sn.axion_note_id NOT IN (
              SELECT DISTINCT job_field_note_id FROM job_note_files
          )
    """).fetchone()[0]
    nf_total = conn.execute("SELECT COUNT(*) FROM job_note_files").fetchone()[0]
    result["staged_files_mapped_missing_jnf"] = mapped_no_jnf

    import collections as _collections
    file_rows = conn.execute(
        "SELECT file_name FROM geoop_staging_notes WHERE file_name IS NOT NULL AND file_name != ''"
    ).fetchall()
    ext_counts = _collections.Counter()
    for fr in file_rows:
        fn = fr[0]
        dot = fn.rfind(".")
        ext = fn[dot + 1:].lower() if dot >= 0 else "(none)"
        ext_counts[ext] += 1
    result["file_types"] = dict(ext_counts.most_common(20))

    staging_files = conn.execute("SELECT COUNT(*) FROM geoop_staging_files").fetchone()[0]
    result["staging_files_manifest"] = staging_files

    if staging_files > 0:
        sf_status = conn.execute(
            "SELECT import_status, COUNT(*) c FROM geoop_staging_files GROUP BY import_status ORDER BY c DESC"
        ).fetchall()
        result["staging_files_by_status"] = {r[0]: r[1] for r in sf_status}

    doc_total = conn.execute("SELECT COUNT(*) FROM job_documents").fetchone()[0]
    result["job_documents_total"] = doc_total
    doc_linked = conn.execute("SELECT COUNT(*) FROM job_documents WHERE job_id IS NOT NULL").fetchone()[0]
    result["job_documents_linked"] = doc_linked

    result["job_note_files_total"] = nf_total
    nf_linked = conn.execute("""
        SELECT COUNT(*) FROM job_note_files jnf
        JOIN job_field_notes jfn ON jfn.id = jnf.job_field_note_id
    """).fetchone()[0]
    result["job_note_files_linked"] = nf_linked
    result["job_note_files_orphaned"] = nf_total - nf_linked

    try:
        unmatched_total = conn.execute("SELECT COUNT(*) FROM geoop_unmatched_attachments").fetchone()[0]
        result["unmatched_attachments_total"] = unmatched_total
        if unmatched_total > 0:
            by_reason = conn.execute(
                "SELECT reason, COUNT(*) c FROM geoop_unmatched_attachments GROUP BY reason ORDER BY c DESC"
            ).fetchall()
            result["unmatched_by_reason"] = {r[0]: r[1] for r in by_reason}
    except Exception:
        result["unmatched_attachments_total"] = 0

    failed_reasons = []
    unmatched_notes = conn.execute("""
        SELECT geoop_job_id, geoop_note_id, file_name, files_location, import_status, error_message
        FROM geoop_staging_notes
        WHERE file_name IS NOT NULL AND file_name != ''
          AND import_status NOT IN ('imported', 'pending', 'linked_to_parent')
        LIMIT 50
    """).fetchall()
    for n in unmatched_notes:
        failed_reasons.append({
            "geoop_job_id": n["geoop_job_id"],
            "geoop_note_id": n["geoop_note_id"],
            "file_name": n["file_name"],
            "import_status": n["import_status"],
            "error": n["error_message"] or "",
        })
    result["failed_file_notes_sample"] = failed_reasons

    geoop_note_files = 0
    try:
        geoop_note_files = conn.execute("""
            SELECT COUNT(*) FROM geoop_staging_files WHERE source_type='azure_blob' AND import_status='imported'
        """).fetchone()[0]
    except Exception:
        pass

    result["pipeline_status"] = {
        "stage_1_notes_csv": "complete" if total_notes > 0 else "not_run",
        "stage_2_note_import": "complete" if result["notes_by_status"].get("imported", 0) > 0 else "not_run",
        "stage_3_azure_scan": "complete" if staging_files > 0 else "not_run",
        "stage_4_file_import": "complete" if geoop_note_files > 0 else "not_run",
    }

    return result


def backfill_attachment_links(run_id=None):
    import time
    conn = _db()
    ensure_staging_tables(conn)
    ts = _now()

    stats = {
        "status": "running",
        "notes_relinked": 0,
        "files_relinked": 0,
        "already_linked": 0,
        "no_matching_job": 0,
        "errors": 0,
    }

    if run_id:
        _persist_scan_progress(run_id, stats)

    try:
        job_map = {}
        job_date_map = {}
        for r in conn.execute("""
            SELECT geoop_job_id, axion_job_id, date_modified, date_created
            FROM geoop_staging_jobs WHERE axion_job_id IS NOT NULL
        """).fetchall():
            job_map[r["geoop_job_id"]] = r["axion_job_id"]
            job_date_map[r["geoop_job_id"]] = r["date_modified"] or r["date_created"] or ""

        batch_size = 2000
        last_id = 0
        while True:
            notes = conn.execute("""
                SELECT id, geoop_job_id, geoop_note_id, note_description, file_name, file_date,
                       files_location, import_status, axion_job_id, axion_note_id
                FROM geoop_staging_notes
                WHERE id > ?
                  AND import_status IN ('unmatched_job', 'skipped_empty', 'error')
                  AND file_name IS NOT NULL AND file_name != ''
                ORDER BY id LIMIT ?
            """, (last_id, batch_size)).fetchall()

            if not notes:
                break

            for note in notes:
                last_id = note["id"]
                axion_job_id = job_map.get(note["geoop_job_id"])
                if not axion_job_id:
                    stats["no_matching_job"] += 1
                    if note["import_status"] != "unmatched_job":
                        conn.execute(
                            "UPDATE geoop_staging_notes SET import_status='unmatched_job', imported_at=? WHERE id=?",
                            (ts, note["id"])
                        )
                    continue

                if note["axion_note_id"]:
                    exists = conn.execute(
                        "SELECT 1 FROM job_field_notes WHERE id=?", (note["axion_note_id"],)
                    ).fetchone()
                    if exists:
                        stats["already_linked"] += 1
                        continue

                note_text = (note["note_description"] or "").strip()
                has_file = bool((note["file_name"] or "").strip())
                if not note_text and not has_file:
                    continue

                if has_file and not note_text:
                    files_loc = (note["files_location"] or "").strip().strip("/")
                    loc_parts = files_loc.split("/")
                    if len(loc_parts) >= 3 and loc_parts[2] != note["geoop_note_id"]:
                        parent_id = loc_parts[2]
                        parent = conn.execute(
                            "SELECT axion_note_id FROM geoop_staging_notes WHERE geoop_note_id=?",
                            (parent_id,)
                        ).fetchone()
                        parent_axion_id = parent["axion_note_id"] if parent else None
                        conn.execute(
                            "UPDATE geoop_staging_notes SET import_status='linked_to_parent', axion_job_id=?, axion_note_id=?, imported_at=? WHERE id=?",
                            (axion_job_id, parent_axion_id, ts, note["id"])
                        )
                        stats["already_linked"] += 1
                        continue
                    note_text = "[Attachment: " + (note["file_name"] or "file") + "]"

                raw_date = note["file_date"] or ""
                note_date = None
                if raw_date:
                    note_date = _utc_to_melb(raw_date)
                if not note_date:
                    note_date = _parse_note_text_date(note_text)
                if not note_date:
                    fallback = job_date_map.get(note["geoop_job_id"], "")
                    if fallback:
                        note_date = _utc_to_melb(fallback)
                if not note_date:
                    note_date = ts

                try:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO job_field_notes (job_id, created_by_user_id, note_text, created_at, note_type)
                        VALUES (?, 1, ?, ?, 'text')
                    """, (axion_job_id, note_text, note_date))
                    new_note_id = cur.lastrowid

                    conn.execute(
                        "UPDATE geoop_staging_notes SET import_status='imported', axion_job_id=?, axion_note_id=?, imported_at=? WHERE id=?",
                        (axion_job_id, new_note_id, ts, note["id"])
                    )
                    stats["notes_relinked"] += 1

                    if (note["file_name"] or "").strip():
                        _ensure_job_note_file(conn, new_note_id, note, ts)
                except Exception as e:
                    conn.execute(
                        "UPDATE geoop_staging_notes SET import_status='error', error_message=?, imported_at=? WHERE id=?",
                        (str(e)[:500], ts, note["id"])
                    )
                    stats["errors"] += 1

            conn.commit()
            if run_id:
                _persist_scan_progress(run_id, stats)

        _reconcile_linked_to_parent(conn)
        _link_staged_attachments(conn)
        stats["status"] = "completed"
    except Exception as e:
        stats["status"] = "failed"
        stats["error_message"] = str(e)[:500]

    if run_id:
        try:
            conn.execute(
                "UPDATE geoop_import_runs SET status=?, completed_at=? WHERE id=?",
                (stats["status"], _now(), run_id)
            )
            conn.commit()
        except Exception:
            pass
        _persist_scan_progress(run_id, stats)

    conn.close()
    return stats


_repair_dates_lock = threading.Lock()
_repair_dates_progress = {"status": "idle", "updated": 0, "skipped": 0, "total": 0}


def get_repair_dates_progress():
    return dict(_repair_dates_progress)


def repair_note_dates():
    if not _repair_dates_lock.acquire(blocking=False):
        return False
    _repair_dates_progress.clear()
    _repair_dates_progress.update({"status": "running", "updated": 0, "skipped": 0, "text_parsed": 0, "total": 0})

    def _run():
        import logging
        log = logging.getLogger("geoop_import")
        try:
            conn = _db()
            try:
                updated = 0
                skipped = 0
                text_parsed = 0

                job_date_map = {}
                for r in conn.execute("""
                    SELECT geoop_job_id, date_modified, date_created
                    FROM geoop_staging_jobs
                """).fetchall():
                    job_date_map[r["geoop_job_id"]] = r["date_modified"] or r["date_created"] or ""

                rows = conn.execute("""
                    SELECT sn.axion_note_id, sn.file_date, sn.geoop_job_id, sn.note_description
                    FROM geoop_staging_notes sn
                    WHERE sn.axion_note_id IS NOT NULL
                      AND sn.import_status = 'imported'
                """).fetchall()

                _repair_dates_progress["total"] = len(rows)
                log.info("Repair note dates: %d notes to process", len(rows))

                seen_note_ids = set()
                batch = []
                for r in rows:
                    nid = r["axion_note_id"]
                    if nid in seen_note_ids:
                        continue
                    seen_note_ids.add(nid)

                    clean_date = None
                    raw_date = r["file_date"] or ""
                    if raw_date:
                        clean_date = _utc_to_melb(raw_date)

                    if not clean_date:
                        parsed = _parse_note_text_date(r["note_description"])
                        if parsed:
                            clean_date = parsed
                            text_parsed += 1

                    if not clean_date:
                        fallback = job_date_map.get(r["geoop_job_id"], "")
                        if fallback:
                            clean_date = _utc_to_melb(fallback)

                    if not clean_date:
                        skipped += 1
                        continue

                    batch.append((clean_date, nid))

                    if len(batch) >= 500:
                        conn.executemany(
                            "UPDATE job_field_notes SET created_at = ? WHERE id = ?",
                            batch
                        )
                        conn.commit()
                        updated += len(batch)
                        _repair_dates_progress["updated"] = updated
                        _repair_dates_progress["text_parsed"] = text_parsed
                        batch = []

                if batch:
                    conn.executemany(
                        "UPDATE job_field_notes SET created_at = ? WHERE id = ?",
                        batch
                    )
                    conn.commit()
                    updated += len(batch)

                _repair_dates_progress.update({
                    "status": "complete", "updated": updated, "skipped": skipped,
                    "text_parsed": text_parsed,
                })
                log.info("Repair note dates complete: %d updated, %d skipped, %d parsed from text",
                         updated, skipped, text_parsed)
            finally:
                conn.close()
        except Exception as e:
            log.error("Repair note dates failed: %s", e)
            _repair_dates_progress.update({"status": "error", "error": str(e)[:500]})
        finally:
            _repair_dates_lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return True


_repair_job_dates_lock = threading.Lock()
_repair_job_dates_progress = {"status": "idle", "updated": 0, "total": 0}


def get_repair_job_dates_progress():
    return dict(_repair_job_dates_progress)


def repair_job_dates():
    if not _repair_job_dates_lock.acquire(blocking=False):
        return False
    _repair_job_dates_progress.clear()
    _repair_job_dates_progress.update({"status": "running", "updated": 0, "total": 0})

    def _run():
        import logging
        log = logging.getLogger("geoop_import")
        try:
            conn = _db()
            try:
                rows = conn.execute("""
                    SELECT sj.axion_job_id, sj.date_created, sj.date_modified
                    FROM geoop_staging_jobs sj
                    WHERE sj.axion_job_id IS NOT NULL
                      AND (sj.date_created IS NOT NULL AND sj.date_created != '')
                """).fetchall()

                _repair_job_dates_progress["total"] = len(rows)
                log.info("Repair job dates: %d jobs to process", len(rows))

                batch = []
                for r in rows:
                    raw_created = r["date_created"] or ""
                    raw_modified = r["date_modified"] or raw_created
                    try:
                        dt_created = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
                        clean_created = dt_created.strftime("%Y-%m-%dT%H:%M:%S")
                    except (ValueError, AttributeError):
                        continue
                    try:
                        dt_modified = datetime.fromisoformat(raw_modified.replace("Z", "+00:00"))
                        clean_modified = dt_modified.strftime("%Y-%m-%dT%H:%M:%S")
                    except (ValueError, AttributeError):
                        clean_modified = clean_created

                    batch.append((clean_created, clean_modified, r["axion_job_id"]))

                    if len(batch) >= 500:
                        conn.executemany(
                            "UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?",
                            batch
                        )
                        conn.commit()
                        _repair_job_dates_progress["updated"] += len(batch)
                        batch = []

                if batch:
                    conn.executemany(
                        "UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?",
                        batch
                    )
                    conn.commit()
                    _repair_job_dates_progress["updated"] += len(batch)

                _repair_job_dates_progress["status"] = "complete"
                log.info("Repair job dates complete: %d updated", _repair_job_dates_progress["updated"])
            finally:
                conn.close()
        except Exception as e:
            log.error("Repair job dates failed: %s", e)
            _repair_job_dates_progress.update({"status": "error", "error": str(e)[:500]})
        finally:
            _repair_job_dates_lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return True


_repair_phones_lock = threading.Lock()
_repair_phones_progress = {"status": "idle", "updated": 0, "total": 0}


def get_repair_phones_progress():
    return dict(_repair_phones_progress)


_repair_reg_lock = threading.Lock()
_repair_reg_progress = {"status": "idle"}

def get_repair_reg_progress():
    return dict(_repair_reg_progress)

def repair_registrations():
    if not _repair_reg_lock.acquire(blocking=False):
        return False
    _repair_reg_progress.clear()
    _repair_reg_progress.update({"status": "running", "staging_fixed": 0, "items_fixed": 0, "total": 0})

    def _run():
        import logging
        log = logging.getLogger("geoop_import")
        try:
            conn = _db()
            try:
                staging_rows = conn.execute("""
                    SELECT id, raw_description, parsed_reg
                    FROM geoop_staging_jobs
                    WHERE raw_description IS NOT NULL AND raw_description != ''
                      AND import_status IN ('imported', 'updated')
                """).fetchall()
                staging_batch = []
                for r in staging_rows:
                    parsed = parse_description(r["raw_description"])
                    new_reg = parsed.get("parsed_reg", "")
                    old_reg = r["parsed_reg"] or ""
                    if new_reg != old_reg:
                        staging_batch.append((new_reg, r["id"]))
                if staging_batch:
                    conn.executemany(
                        "UPDATE geoop_staging_jobs SET parsed_reg = ? WHERE id = ?",
                        staging_batch
                    )
                    conn.commit()
                _repair_reg_progress["staging_fixed"] = len(staging_batch)

                ji_rows = conn.execute("""
                    SELECT ji.id, ji.job_id, ji.reg,
                           j.geoop_source_description AS desc_text
                    FROM job_items ji
                    JOIN jobs j ON j.id = ji.job_id
                    WHERE ji.item_type = 'vehicle'
                      AND j.geoop_source_description IS NOT NULL
                      AND j.geoop_source_description != ''
                """).fetchall()
                _repair_reg_progress["total"] = len(ji_rows)
                log.info("Repair registrations: %d geoop-sourced job_items to check", len(ji_rows))

                _bad_reg_suffixes = ("ULATED", "GULATED", "EGULATED", "REGULATED", "NREGULATED")
                def _is_bad_reg(val):
                    if not val:
                        return False
                    v = val.upper()
                    if v in _bad_reg_suffixes:
                        return True
                    if v.endswith("VIN"):
                        return True
                    return False
                items_actually_updated = 0
                for r in ji_rows:
                    parsed = parse_description(r["desc_text"])
                    new_reg = parsed.get("parsed_reg", "")
                    old_reg = r["reg"] or ""
                    if old_reg and not _is_bad_reg(old_reg) and old_reg == new_reg:
                        continue
                    safe_to_update = (
                        not old_reg
                        or _is_bad_reg(old_reg)
                    )
                    if not safe_to_update:
                        continue
                    new_val = new_reg or ""
                    if new_val == old_reg:
                        continue
                    cur = conn.execute(
                        "UPDATE job_items SET reg = ? WHERE id = ?",
                        (new_val, r["id"])
                    )
                    items_actually_updated += cur.rowcount
                conn.commit()
                _repair_reg_progress["items_fixed"] = items_actually_updated

                _repair_reg_progress["status"] = "complete"
                log.info("Repair registrations complete: %d staging, %d items fixed",
                         len(staging_batch), items_actually_updated)
            finally:
                conn.close()
        except Exception as e:
            log.error("Repair registrations failed: %s", e)
            _repair_reg_progress.update({"status": "error", "error": str(e)[:500]})
        finally:
            _repair_reg_lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return True


_repair_due_dates_lock = threading.Lock()
_repair_due_dates_progress = {"status": "idle"}

def get_repair_due_dates_progress():
    return dict(_repair_due_dates_progress)

def repair_due_dates():
    if not _repair_due_dates_lock.acquire(blocking=False):
        return False
    _repair_due_dates_progress.clear()
    _repair_due_dates_progress.update({"status": "running", "staging_fixed": 0, "jobs_fixed": 0, "total": 0})

    def _run():
        import logging
        log = logging.getLogger("geoop_import")
        try:
            conn = _db()
            try:
                staging_rows = conn.execute("""
                    SELECT id, raw_description, parsed_nmpd_date, parsed_nmpd_amount_cents
                    FROM geoop_staging_jobs
                    WHERE raw_description IS NOT NULL AND raw_description != ''
                      AND import_status IN ('imported', 'updated')
                """).fetchall()
                staging_batch = []
                for r in staging_rows:
                    parsed = parse_description(r["raw_description"])
                    new_date = parsed.get("parsed_nmpd_date", "")
                    new_amount = parsed.get("parsed_nmpd_amount_cents", 0) or 0
                    old_date = r["parsed_nmpd_date"] or ""
                    if new_date != old_date:
                        staging_batch.append((new_date, new_amount, r["id"]))
                if staging_batch:
                    conn.executemany(
                        "UPDATE geoop_staging_jobs SET parsed_nmpd_date = ?, parsed_nmpd_amount_cents = ? WHERE id = ?",
                        staging_batch
                    )
                    conn.commit()
                _repair_due_dates_progress["staging_fixed"] = len(staging_batch)
                log.info("Repair due dates: %d staging rows fixed", len(staging_batch))

                job_rows = conn.execute("""
                    SELECT j.id, j.job_due_date, j.mmp_cents,
                           j.geoop_source_description AS desc_text
                    FROM jobs j
                    WHERE j.geoop_source_description IS NOT NULL
                      AND j.geoop_source_description != ''
                """).fetchall()
                _repair_due_dates_progress["total"] = len(job_rows)
                log.info("Repair due dates: %d geoop-sourced jobs to check", len(job_rows))

                jobs_actually_updated = 0
                for r in job_rows:
                    desc = r["desc_text"]
                    old_date = r["job_due_date"] or ""

                    parsed = parse_description(desc)
                    new_date = parsed.get("parsed_nmpd_date", "")
                    new_amount = parsed.get("parsed_nmpd_amount_cents", 0) or 0

                    if not new_date:
                        continue

                    old_normalised = old_date
                    old_is_raw = bool(re.match(r'^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}$', old_date))
                    if old_is_raw:
                        old_normalised = _normalise_au_date(old_date)

                    if new_date == old_normalised:
                        continue

                    _rep_freq = "Monthly" if new_date else ""
                    cur = conn.execute("""
                        UPDATE jobs SET job_due_date = ?, mmp_cents = ?,
                            payment_frequency = COALESCE(NULLIF(payment_frequency, ''), ?)
                        WHERE id = ?
                    """, (new_date, new_amount, _rep_freq, r["id"]))
                    jobs_actually_updated += cur.rowcount

                conn.commit()
                _repair_due_dates_progress["jobs_fixed"] = jobs_actually_updated

                _repair_due_dates_progress["status"] = "complete"
                log.info("Repair due dates complete: %d staging, %d jobs fixed",
                         len(staging_batch), jobs_actually_updated)
            finally:
                conn.close()
        except Exception as e:
            log.error("Repair due dates failed: %s", e)
            _repair_due_dates_progress.update({"status": "error", "error": str(e)[:500]})
        finally:
            _repair_due_dates_lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return True


def repair_phone_numbers():
    if not _repair_phones_lock.acquire(blocking=False):
        return False
    _repair_phones_progress.clear()
    _repair_phones_progress.update({"status": "running", "updated": 0, "total": 0})

    def _run():
        import logging
        log = logging.getLogger("geoop_import")
        try:
            conn = _db()
            try:
                rows = conn.execute("""
                    SELECT id, phone_number FROM contact_phone_numbers
                    WHERE phone_number IS NOT NULL AND phone_number != ''
                """).fetchall()
                _repair_phones_progress["total"] = len(rows)
                log.info("Repair phone numbers: %d rows to check", len(rows))

                batch = []
                for r in rows:
                    original = r["phone_number"]
                    fixed = _preserve_phone_text(original)
                    if fixed != original:
                        batch.append((fixed, r["id"]))

                    if len(batch) >= 500:
                        conn.executemany(
                            "UPDATE contact_phone_numbers SET phone_number = ? WHERE id = ?",
                            batch
                        )
                        conn.commit()
                        _repair_phones_progress["updated"] += len(batch)
                        batch = []

                if batch:
                    conn.executemany(
                        "UPDATE contact_phone_numbers SET phone_number = ? WHERE id = ?",
                        batch
                    )
                    conn.commit()
                    _repair_phones_progress["updated"] += len(batch)

                staging_rows = conn.execute("""
                    SELECT id, phone, mobile FROM geoop_staging_jobs
                    WHERE (phone IS NOT NULL AND phone != '') OR (mobile IS NOT NULL AND mobile != '')
                """).fetchall()
                staging_batch = []
                for r in staging_rows:
                    phone_fixed = _preserve_phone_text(r["phone"] or "")
                    mobile_fixed = _preserve_phone_text(r["mobile"] or "")
                    if phone_fixed != (r["phone"] or "") or mobile_fixed != (r["mobile"] or ""):
                        staging_batch.append((phone_fixed, mobile_fixed, r["id"]))
                if staging_batch:
                    conn.executemany(
                        "UPDATE geoop_staging_jobs SET phone = ?, mobile = ? WHERE id = ?",
                        staging_batch
                    )
                    conn.commit()
                    log.info("Repair phones: fixed %d staging rows", len(staging_batch))

                _repair_phones_progress["status"] = "complete"
                log.info("Repair phone numbers complete: %d updated", _repair_phones_progress["updated"])
            finally:
                conn.close()
        except Exception as e:
            log.error("Repair phone numbers failed: %s", e)
            _repair_phones_progress.update({"status": "error", "error": str(e)[:500]})
        finally:
            _repair_phones_lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return True
