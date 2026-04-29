#!/usr/bin/env python3
"""
AxionX Demo Database Seed Script
=================================
Initialises axion_demo.db with the full schema and realistic fake data.

Usage:
    python3 scripts/seed_demo.py          # seed only (skip if tables exist)
    python3 scripts/seed_demo.py --reset  # drop and recreate from scratch

Environment variables:
    AXIONX_DEMO_DB_PATH  — path to the demo database (default: ./axion_demo.db)

SAFETY: This script NEVER imports from or writes to axion.db.
"""

import argparse
import os
import sys
import sqlite3
from datetime import datetime, timedelta

# ── Resolve demo DB path ────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
# Accept AXIONX_DB_PATH (original spec) or AXIONX_DEMO_DB_PATH (alias).
_demo_db_default = os.path.join(_ROOT, "axion_demo.db")
DEMO_DB_PATH = os.path.abspath(
    os.environ.get("AXIONX_DEMO_DB_PATH")
    or os.environ.get("AXIONX_DB_PATH")
    or _demo_db_default
)

# ── Safety guard ────────────────────────────────────────────────────────────
_PROD_CANDIDATES = {"axion.db", "database.db"}
if os.path.basename(DEMO_DB_PATH) in _PROD_CANDIDATES:
    print(f"[SAFETY] Refusing to write to suspected production DB: {DEMO_DB_PATH}", file=sys.stderr)
    sys.exit(1)

print(f"[SEED] Demo DB path: {DEMO_DB_PATH}")


def _conn():
    c = sqlite3.connect(DEMO_DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    # Use DELETE journal mode during seeding to avoid WAL lock conflicts with a
    # running app instance.  The app will switch it to WAL on first connect.
    c.execute("PRAGMA journal_mode=DELETE")
    c.execute("PRAGMA foreign_keys=OFF")
    return c


def now_ts():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def ts(days_ago=0, hours_ago=0):
    dt = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# ── Schema creation (dynamic — copies DDL from production DB) ───────────────

# The demo_outbox table exists only in the demo DB.
_DEMO_OUTBOX_DDL = """
CREATE TABLE IF NOT EXISTS demo_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_type TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""

# Persistent reset audit log — survives across resets because it is recreated
# and populated with the triggering event immediately after each seed run.
_DEMO_RESET_LOG_DDL = """
CREATE TABLE IF NOT EXISTS demo_reset_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reset_at    TEXT NOT NULL,
    triggered_by TEXT NOT NULL DEFAULT 'demo_admin',
    role        TEXT NOT NULL DEFAULT 'demo_admin',
    ip_address  TEXT,
    outcome     TEXT NOT NULL DEFAULT 'success',
    notes       TEXT
);
"""

# Schemas that are not in production but that older hand-written versions of
# seed_demo.py created.  We keep them here as fallbacks in case axion.db is
# unavailable.
_LEGACY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT '',
    nickname TEXT
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    company TEXT,
    email TEXT,
    dob TEXT,
    address TEXT,
    notes TEXT,
    id_image_filename TEXT,
    id_image_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT '',
    role TEXT
);

CREATE TABLE IF NOT EXISTS customer_addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    address TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT 'Primary',
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contact_phone_numbers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contact_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    label TEXT,
    email TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS booking_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    job_prefix TEXT NOT NULL,
    job_sequence INTEGER NOT NULL,
    auto_prefix_enabled INTEGER NOT NULL DEFAULT 1,
    email_signature TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    internal_job_number TEXT NOT NULL,
    client_reference TEXT,
    display_ref TEXT NOT NULL,
    client_id INTEGER,
    customer_id INTEGER,
    assigned_user_id INTEGER,
    job_type TEXT NOT NULL,
    visit_type TEXT NOT NULL,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    job_address TEXT,
    description TEXT,
    lender_name TEXT,
    account_number TEXT,
    regulation_type TEXT,
    arrears_cents INTEGER,
    costs_cents INTEGER,
    mmp_cents INTEGER,
    job_due_date TEXT,
    payment_frequency TEXT,
    tp_referral TEXT,
    tp_job_number TEXT,
    lat REAL,
    lng REAL,
    bill_to_client_id INTEGER,
    client_job_number TEXT,
    deliver_to TEXT,
    geoop_job_id TEXT,
    geoop_source_description TEXT,
    geoop_assigned_agent TEXT,
    costs2_cents INTEGER,
    geocode_fail INTEGER DEFAULT 0,
    status_changed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    description TEXT,
    reg TEXT,
    vin TEXT,
    make TEXT,
    model TEXT,
    year TEXT,
    property_address TEXT,
    lot_details TEXT,
    serial_number TEXT,
    identifier TEXT,
    engine_number TEXT,
    colour TEXT,
    deliver_to TEXT,
    lender_name TEXT,
    account_number TEXT,
    regulation_type TEXT,
    arrears_cents INTEGER DEFAULT 0,
    costs_cents INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL DEFAULT 'Other',
    description TEXT,
    rego TEXT,
    vin TEXT,
    make TEXT,
    model TEXT,
    year TEXT,
    address TEXT,
    serial TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'Primary',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(job_id, customer_id)
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    narrative TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    photo_path TEXT
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    booking_type_id INTEGER NOT NULL,
    scheduled_for TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Booked',
    notes TEXT,
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL,
    assigned_to_user_id INTEGER,
    hidden INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cue_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    visit_type TEXT NOT NULL,
    due_date TEXT NOT NULL,
    time_window_start TEXT,
    time_window_end TEXT,
    priority TEXT NOT NULL DEFAULT 'Normal',
    status TEXT NOT NULL DEFAULT 'Pending',
    assigned_user_id INTEGER,
    instructions TEXT,
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS job_field_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    created_by_user_id INTEGER,
    note_text TEXT,
    created_at TEXT NOT NULL,
    note_type TEXT NOT NULL DEFAULT 'text',
    audio_filename TEXT,
    updated_at TEXT,
    updated_by_user_id INTEGER,
    review_status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS job_note_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_field_note_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    file_status TEXT NOT NULL DEFAULT 'ok'
);

CREATE TABLE IF NOT EXISTS job_office_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    note_body TEXT NOT NULL,
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL,
    updated_by_user_id INTEGER,
    updated_at TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS job_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    created_by_user_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft',
    attend_date TEXT,
    attend_time TEXT,
    is_first_attendance INTEGER NOT NULL DEFAULT 0,
    property_description TEXT,
    security_sighted INTEGER NOT NULL DEFAULT 0,
    security_make_model TEXT,
    security_reg TEXT,
    security_location TEXT,
    calling_card INTEGER NOT NULL DEFAULT 0,
    neighbour_outcome TEXT,
    call_made INTEGER NOT NULL DEFAULT 0,
    call_outcome TEXT,
    voicemail_left INTEGER NOT NULL DEFAULT 0,
    sms_sent INTEGER NOT NULL DEFAULT 0,
    customer_mobile TEXT,
    points_of_contact INTEGER NOT NULL DEFAULT 0,
    eta_next_date TEXT,
    generated_narrative TEXT,
    final_narrative TEXT,
    narrative_edited INTEGER NOT NULL DEFAULT 0,
    structured_inputs_json TEXT,
    ai_model_used TEXT,
    ai_tokens_used INTEGER,
    is_ai_draft INTEGER NOT NULL DEFAULT 0,
    agent_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_lifecycle_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    actor_user_id INTEGER,
    from_status TEXT,
    to_status TEXT,
    changed_at TEXT NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS job_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    doc_type TEXT NOT NULL,
    title TEXT,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    mime_type TEXT,
    file_size INTEGER,
    uploaded_by_user_id INTEGER,
    uploaded_at TEXT NOT NULL,
    notes TEXT,
    file_status TEXT NOT NULL DEFAULT 'ok'
);

CREATE TABLE IF NOT EXISTS job_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    payment_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    note TEXT,
    recorded_by_user_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repo_lock_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    client_name TEXT,
    client_reference TEXT,
    swpi_ref TEXT,
    finance_company TEXT,
    repo_date TEXT,
    start_time TEXT,
    end_time TEXT,
    customer_name TEXT,
    account_number TEXT,
    repo_address TEXT,
    year TEXT,
    make TEXT,
    model TEXT,
    colour TEXT,
    registration TEXT,
    rego_expiry TEXT,
    vin TEXT,
    engine_number TEXT,
    speedometer TEXT,
    person_present TEXT,
    keys_obtained TEXT,
    how_many_keys TEXT,
    vol_surrender TEXT,
    form_13 TEXT,
    security_drivable TEXT,
    police_notified TEXT,
    station_officer TEXT,
    personal_effects_removed TEXT,
    personal_effects_list TEXT,
    tyres TEXT,
    body TEXT,
    duco TEXT,
    interior TEXT,
    engine_condition TEXT,
    transmission TEXT,
    fuel_level TEXT,
    any_damage TEXT,
    damage_list TEXT,
    agent_name TEXT,
    notice_delivery TEXT,
    agent_sig TEXT,
    customer_sig TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitted_at TEXT,
    submitted_by_user_id INTEGER
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    action TEXT NOT NULL,
    message TEXT NOT NULL,
    meta_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_throttle (
    key TEXT PRIMARY KEY,
    fail_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS urgent_update_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    sched_id INTEGER NOT NULL UNIQUE,
    triggered_by_user_id INTEGER NOT NULL,
    agent_user_id INTEGER NOT NULL,
    triggered_at TEXT NOT NULL,
    message_id INTEGER,
    note_id INTEGER,
    new_sched_id INTEGER
);

CREATE TABLE IF NOT EXISTS agent_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias TEXT NOT NULL UNIQUE,
    user_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    accuracy REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS message_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    actor_user_id INTEGER,
    msg_type TEXT NOT NULL,
    recipient TEXT,
    subject TEXT,
    body_preview TEXT,
    status TEXT NOT NULL DEFAULT 'sent',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recovery_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type TEXT DEFAULT 'Recovery Target',
    status TEXT NOT NULL DEFAULT 'Active',
    created_at TEXT NOT NULL,
    created_by INTEGER,
    updated_at TEXT,
    updated_by INTEGER,
    assigned_agency TEXT,
    assigned_staff_user_id INTEGER,
    internal_reference TEXT,
    agency_reference TEXT,
    lender_reference TEXT,
    liquidator_reference TEXT,
    repossession_active INTEGER NOT NULL DEFAULT 1,
    repossession_completed_at TEXT,
    outcome_note TEXT
);

CREATE TABLE IF NOT EXISTS recovery_target_parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    party_type TEXT,
    organisation_name TEXT,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    reference_number TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS recovery_target_people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    full_legal_name TEXT,
    aliases TEXT,
    date_of_birth TEXT,
    driver_licence_number TEXT,
    licence_state TEXT,
    email_primary TEXT,
    risk_notes TEXT,
    general_notes TEXT
);

CREATE TABLE IF NOT EXISTS recovery_target_phones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    phone_number TEXT,
    label TEXT,
    is_primary INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recovery_target_addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    address TEXT,
    label TEXT,
    is_primary INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recovery_target_vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    rego TEXT,
    vin TEXT,
    make TEXT,
    model TEXT,
    year TEXT,
    colour TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS lpr_watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rego TEXT NOT NULL UNIQUE,
    target_id INTEGER,
    job_id INTEGER,
    priority INTEGER NOT NULL DEFAULT 5,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS lpr_sightings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rego TEXT NOT NULL,
    lat REAL,
    lng REAL,
    address TEXT,
    confidence REAL,
    image_filename TEXT,
    sighted_by_user_id INTEGER,
    sighted_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    notes TEXT,
    matched_job_id INTEGER,
    matched_target_id INTEGER,
    reviewed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS demo_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_type TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_mobile_settings (
    user_id INTEGER PRIMARY KEY,
    list_sort TEXT NOT NULL DEFAULT 'visit_date',
    list_dir TEXT NOT NULL DEFAULT 'asc',
    distance_unit TEXT NOT NULL DEFAULT 'km',
    gps_foreground INTEGER NOT NULL DEFAULT 1,
    gps_bg INTEGER NOT NULL DEFAULT 0,
    gps_interval_mins INTEGER NOT NULL DEFAULT 5,
    updated_at TEXT,
    job_scope TEXT NOT NULL DEFAULT 'mine',
    show_completed TEXT NOT NULL DEFAULT 'week',
    quick_status TEXT NOT NULL DEFAULT '',
    mobile_default_view TEXT NOT NULL DEFAULT 'schedule',
    show_status_on_visits INTEGER NOT NULL DEFAULT 1,
    job_assignment TEXT NOT NULL DEFAULT 'all'
);
"""


def _apply_ddl_string(conn, ddl_sql: str):
    """Split a multi-statement SQL string on ';' and execute each statement."""
    for stmt in ddl_sql.split(";"):
        s = stmt.strip()
        if s:
            try:
                conn.execute(s)
            except Exception as e:
                print(f"[SCHEMA WARN] {e}: {s[:80]}", file=sys.stderr)


def create_schema(conn):
    """
    Apply the demo schema from scripts/demo_schema.sql (committed to the repo).
    Falls back to the hand-written _LEGACY_SCHEMA_SQL if the file is absent.
    The demo_outbox table is always created regardless of source.

    The schema file is generated by scripts/export_demo_schema.py and committed
    to version control. The seed script NEVER reads from axion.db or any
    production database — all schema definitions come from this local file.
    """
    schema_file = os.path.join(_HERE, "demo_schema.sql")
    if os.path.exists(schema_file):
        try:
            with open(schema_file, "r", encoding="utf-8") as fh:
                raw_sql = fh.read()
            count = 0
            for stmt in raw_sql.split(";"):
                stmt = stmt.strip()
                if not stmt or stmt.startswith("--"):
                    continue
                # Ensure CREATE TABLE is idempotent
                if stmt.upper().startswith("CREATE TABLE ") and "IF NOT EXISTS" not in stmt.upper():
                    stmt = stmt.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
                elif stmt.upper().startswith("CREATE INDEX ") and "IF NOT EXISTS" not in stmt.upper():
                    stmt = stmt.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
                elif stmt.upper().startswith("CREATE UNIQUE INDEX ") and "IF NOT EXISTS" not in stmt.upper():
                    stmt = stmt.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
                try:
                    conn.execute(stmt)
                    count += 1
                except Exception as e:
                    print(f"[SCHEMA WARN] {e}: {stmt[:80]}", file=sys.stderr)
            conn.commit()
            print(f"[SEED] Schema applied from {schema_file} ({count} statements).")
        except Exception as e:
            print(f"[SEED] Could not apply {schema_file}: {e}. Falling back to legacy schema.", file=sys.stderr)
            _apply_ddl_string(conn, _LEGACY_SCHEMA_SQL)
            conn.commit()
    else:
        print(f"[SEED] {schema_file} not found — using legacy schema.", file=sys.stderr)
        _apply_ddl_string(conn, _LEGACY_SCHEMA_SQL)
        conn.commit()

    # Always create the demo-only outbox and reset-log tables
    _apply_ddl_string(conn, _DEMO_OUTBOX_DDL)
    _apply_ddl_string(conn, _DEMO_RESET_LOG_DDL)
    conn.commit()
    print("[SEED] Schema created / verified.")


# ── Seed data ───────────────────────────────────────────────────────────────

def seed(conn):
    cur = conn.cursor()

    # ── Reference data
    for jt in ["Repo/Collect", "Collect Only", "Field Call", "Process Serve",
               "Upgrade to Repo/Collect"]:
        cur.execute("INSERT OR IGNORE INTO job_types (name) VALUES (?)", (jt,))

    for bt in ["New Visit", "Re-attend", "Urgent New Visit", "Update Required",
               "Urgent Update Required"]:
        cur.execute("INSERT OR IGNORE INTO booking_types (name) VALUES (?)", (bt,))

    prefix = datetime.now().strftime("%y%m")
    cur.execute("INSERT OR IGNORE INTO system_settings (id, job_prefix, job_sequence, updated_at) VALUES (1, ?, 1000, ?)",
                (prefix, now_ts()))

    # ── Users
    from werkzeug.security import generate_password_hash as _hash

    users = [
        ("Demo Admin",         "demo.admin@axionx.demo", _hash("demo-admin-2026"),  "admin", 1),
        ("Demo Field Agent",   "demo.agent@axionx.demo", _hash("demo-agent-2026"),  "agent", 2),
        # Client/Lender uses admin role to see all jobs filtered by their client.
        # There is no dedicated client portal; admin view + client_id filter is closest.
        ("Demo Client/Lender", "demo.client@axionx.demo", _hash("demo-client-2026"), "admin", 3),
    ]
    user_ids = {}
    for full_name, email, pw, role, order in users:
        cur.execute(
            "INSERT OR IGNORE INTO users (full_name, email, password, role, active, created_at) VALUES (?,?,?,?,1,?)",
            (full_name, email, pw, role, ts(30)),
        )
        row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        user_ids[order] = row["id"] if row else order

    admin_id = user_ids[1]
    agent_id = user_ids[2]

    # ── Clients (lenders / finance companies)
    clients = [
        ("Demo Finance Group",    "1300 000 001", "ops@demofinance.example",      "Level 10, 123 Demo St, Melbourne VIC 3000"),
        ("Apex Auto Credit",      "1300 000 002", "repo@apexauto.example",         "Suite 5, 456 Sample Rd, Southbank VIC 3006"),
        ("First Fleet Finance",   "1300 000 003", "collections@firstfleet.example","PO Box 99, Richmond VIC 3121"),
    ]
    client_ids = []
    for name, phone, email, address in clients:
        cur.execute(
            "INSERT INTO clients (name, phone, email, address, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (name, phone, email, address, ts(60), ts(5)),
        )
        client_ids.append(cur.lastrowid)

    # ── Customers (debtors)
    customer_data = [
        ("James",    "Morrison",   "12 Fake Lane, Footscray VIC 3011",       "0411 111 001"),
        ("Sarah",    "Nguyen",     "77 Sample Ave, Sunshine VIC 3020",       "0422 222 002"),
        ("Marcus",   "Thompson",   "3/55 Demo Blvd, Werribee VIC 3030",      "0433 333 003"),
        ("Linda",    "Patel",      "9 Example St, Hoppers Crossing VIC 3029","0444 444 004"),
        ("David",    "Williams",   "100 Placeholder Dr, St Albans VIC 3021", "0455 555 005"),
        ("Emma",     "Johnson",    "22 Test Rd, Deer Park VIC 3023",         "0466 666 006"),
        ("Kevin",    "Brown",      "8 Dummy Close, Tarneit VIC 3029",        "0477 777 007"),
        ("Rachel",   "Smith",      "41 Fictitious Way, Caroline Springs VIC 3023","0488 888 008"),
        ("Tom",      "Anderson",   "6 Mock St, Melton VIC 3337",             "0499 999 009"),
        ("Jessica",  "Taylor",     "19 Fabricated Ave, Wyndham Vale VIC 3024","0400 100 010"),
        ("Alex",     "Robinson",   "5 Invented Pl, Point Cook VIC 3030",     "0411 200 011"),
        ("Maria",    "Chen",       "88 Generated Rd, Altona VIC 3018",       "0422 300 012"),
    ]
    customer_ids = []
    for fn, ln, addr, ph in customer_data:
        cur.execute(
            "INSERT INTO customers (first_name, last_name, address, created_at, updated_at) VALUES (?,?,?,?,?)",
            (fn, ln, addr, ts(90), ts(10)),
        )
        cid = cur.lastrowid
        customer_ids.append(cid)
        cur.execute(
            "INSERT INTO contact_phone_numbers (entity_type, entity_id, label, phone_number, created_at) VALUES ('customer', ?, 'Mobile', ?, ?)",
            (cid, ph, ts(90)),
        )
        cur.execute(
            "INSERT INTO customer_addresses (customer_id, address, label, is_primary, created_at) VALUES (?,?,?,1,?)",
            (cid, addr, "Primary", ts(90)),
        )

    # ── Vehicles / Items per job
    vehicles = [
        ("VIC", "1ABC234", "1HGCM82633A004352", "Toyota",    "Camry",   "2019", "White",  28500_00),
        ("VIC", "2DEF567", "2HGES16575H536174", "Holden",    "Commodore","2018","Silver", 15200_00),
        ("VIC", "3GHI890", "3VWFE21C04M000001", "Ford",      "Ranger",  "2020", "Black",  42000_00),
        ("VIC", "4JKL123", "4T1BE32K75U609149", "Mazda",     "3",       "2021", "Blue",   24000_00),
        ("VIC", "5MNO456", "5GAKRCED0CJ396916", "Hyundai",   "i30",     "2017", "Red",    12500_00),
        ("VIC", "6PQR789", "6FPAA8CV5BE121234", "Volkswagen","Golf",    "2019", "Grey",   22000_00),
        ("VIC", "7STU012", "7FARW2H54JE040001", "Honda",     "CR-V",    "2018", "White",  31000_00),
        ("VIC", "8VWX345", "8AF3G2A39JD700001", "Kia",       "Sportage","2020", "Blue",   28000_00),
        ("VIC", "9YZA678", "9BWZZZ375VT004251", "Nissan",    "X-Trail", "2016", "Brown",  18000_00),
        ("VIC", "AAB901", "WAUZZZ8K8AA112345", "Audi",       "A4",      "2021", "Black",  55000_00),
        ("VIC", "BBB234", "WBA3A5C50CF256985", "BMW",        "3 Series","2019", "White",  48000_00),
        ("VIC", "CCC567", "WVWZZZ1JZXW100001", "Mercedes",  "C-Class", "2020", "Silver", 62000_00),
    ]

    # ── Jobs ────────────────────────────────────────────────────────────────
    # statuses required: 8 Active, 3 New, 3 Phone Work Only, 2 Repossession Ready,
    #                    1 Completed/Repossessed, 1+ Overdue visits, 2 Pending Review,
    #                    1 Client Update Request, 1 Closure Request

    job_specs = [
        # (seq, status, visit_type, priority, client_idx, cust_idx, veh_idx, description, days_old)
        (1,  "Active",               "Repo/Collect", "Normal",  0, 0,  0,  "Standard active repo, vehicle located nearby",  14),
        (2,  "Active",               "Repo/Collect", "High",    0, 1,  1,  "High priority — debtor attempting to conceal vehicle", 8),
        (3,  "Active",               "Repo/Collect", "Normal",  1, 2,  2,  "Active field case, multiple attendances logged",  20),
        (4,  "Active",               "Repo/Collect", "Normal",  1, 3,  3,  "Active — awaiting next scheduled visit",  6),
        (5,  "Active",               "Repo/Collect", "Urgent",  2, 4,  4,  "Urgent active — lender escalated this morning", 3),
        (6,  "Active",               "Field Call",   "Normal",  0, 5,  5,  "Active field call, process serve pending",  11),
        (7,  "Active",               "Repo/Collect", "Normal",  1, 6,  6,  "Active — vehicle confirmed at address",  17),
        (8,  "Active",               "Repo/Collect", "Normal",  2, 7,  7,  "Active — first attendance scheduled today",  2),
        (9,  "New",                  "Repo/Collect", "Normal",  0, 8,  8,  "New job received from lender portal",  1),
        (10, "New",                  "Repo/Collect", "High",    1, 9,  9,  "New urgent repo — lender marked high priority", 0),
        (11, "New",                  "Field Call",   "Normal",  2, 10, 10, "New field call — process serve instruction",  0),
        (12, "Phone Work Only",      "Repo/Collect", "Normal",  0, 11, 11, "Phone-only — debtor in contact, negotiating",  25),
        (13, "Phone Work Only",      "Repo/Collect", "Normal",  1, 0,  0,  "Phone-only — conducting skip-trace calls",  18),
        (14, "Phone Work Only",      "Field Call",   "Normal",  2, 1,  1,  "Phone-only — awaiting callback from debtor",  12),
        (15, "Repossession Ready",   "Repo/Collect", "High",    0, 2,  2,  "Repo ready — all documentation approved",  5),
        (16, "Repossession Ready",   "Repo/Collect", "Urgent",  1, 3,  3,  "Repo ready — VIR template generated, awaiting tow",  3),
        (17, "Repossessed",          "Repo/Collect", "Normal",  2, 4,  4,  "Completed repossession — vehicle secured, VIR signed", 10),
        (18, "Active",               "Repo/Collect", "Normal",  0, 5,  5,  "Overdue — update required, last attended 22 days ago", 22),
        (19, "Active",               "Repo/Collect", "High",    1, 6,  6,  "Overdue — agent visit overdue by 2 weeks",  14),
    ]

    bt_rows = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM booking_types").fetchall()}

    job_ids = {}
    for (seq, status, jtype, priority, cli_idx, cust_idx, veh_idx, desc, days_old) in job_specs:
        client_id   = client_ids[cli_idx % len(client_ids)]
        customer_id = customer_ids[cust_idx % len(customer_ids)]
        veh         = vehicles[veh_idx % len(vehicles)]
        state, rego, vin, make, model, year, colour, arrears = veh
        cust_row    = customer_data[cust_idx % len(customer_data)]
        cust_addr   = cust_row[2]
        job_ref     = f"DEMO{seq:04d}"
        client_obj  = clients[cli_idx % len(clients)]
        lender_name = client_obj[0]

        cur.execute("""
            INSERT INTO jobs (
                internal_job_number, client_reference, display_ref,
                client_id, customer_id, assigned_user_id,
                job_type, visit_type, status, priority,
                job_address, description,
                lender_name, account_number, arrears_cents,
                created_at, updated_at, status_changed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            job_ref, f"CLI-REF-{seq:04d}", job_ref,
            client_id, customer_id, agent_id,
            jtype, jtype, status, priority,
            cust_addr, desc,
            lender_name, f"ACC-{seq:06d}", arrears,
            ts(days_old), ts(days_old // 2), ts(days_old),
        ))
        job_id = cur.lastrowid
        job_ids[seq] = job_id

        cur.execute("""
            INSERT INTO job_items (
                job_id, item_type, reg, vin, make, model, year, colour,
                arrears_cents, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (job_id, "Vehicle", rego, vin, make, model, year, colour, arrears, ts(days_old)))
        item_id = cur.lastrowid

        cur.execute(
            "INSERT OR IGNORE INTO job_customers (job_id, customer_id, role, sort_order, created_at) VALUES (?,?,?,0,?)",
            (job_id, customer_id, "Primary", ts(days_old)),
        )

        # Add a schedule for active/new jobs
        if status in ("Active", "New", "Repossession Ready"):
            sched_days = 1 if seq <= 8 else -2
            bt_id = bt_rows.get("New Visit", 1)
            if seq in (18, 19):
                sched_days = -days_old + 2
                bt_id = bt_rows.get("Update Required", bt_rows.get("New Visit", 1))
            cur.execute("""
                INSERT INTO schedules (job_id, booking_type_id, scheduled_for, status,
                    created_by_user_id, created_at, assigned_to_user_id)
                VALUES (?,?,?,?,?,?,?)
            """, (
                job_id, bt_id,
                (datetime.now() + timedelta(days=sched_days)).strftime("%Y-%m-%dT09:00:00"),
                "Booked", admin_id, ts(days_old), agent_id,
            ))

        # Office notes
        cur.execute(
            "INSERT INTO job_office_notes (job_id, note_body, created_by_user_id, created_at) VALUES (?,?,?,?)",
            (job_id, f"[DEMO] Initial instructions for job {job_ref}. All data is fictional.", admin_id, ts(days_old)),
        )

        # Field notes for active jobs with history
        if status == "Active" and days_old >= 8:
            cur.execute("""
                INSERT INTO job_field_notes (job_id, created_by_user_id, note_text, created_at, review_status)
                VALUES (?,?,?,?,?)
            """, (
                job_id, agent_id,
                f"Attended address. Vehicle not present. Left calling card. Will re-attend tomorrow.",
                ts(days_old - 2), "pending" if seq in (1, 2, 3, 4) else "reviewed",
            ))

    # ── VIR / repo lock for completed job (seq 17)
    repo_job_id  = job_ids.get(17)
    repo_item_id = conn.execute("SELECT id FROM job_items WHERE job_id=?", (repo_job_id,)).fetchone()
    if repo_item_id:
        cust = customer_data[4]
        veh  = vehicles[4]
        cur.execute("""
            INSERT INTO repo_lock_records (
                job_id, item_id, client_name, client_reference, swpi_ref,
                finance_company, repo_date, start_time, end_time,
                customer_name, account_number, repo_address,
                year, make, model, registration, vin,
                keys_obtained, vol_surrender, form_13, security_drivable,
                police_notified, personal_effects_removed,
                tyres, body, duco, interior, engine_condition, transmission,
                fuel_level, any_damage, agent_name, agent_user_id,
                created_at, updated_at, submitted_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            repo_job_id, repo_item_id["id"],
            "Demo Finance Group", "CLI-REF-0017", "DEMO0017",
            "Demo Finance Group",
            (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
            "10:30", "11:15",
            f"{cust[0]} {cust[1]}", "ACC-000017",
            cust[2],
            veh[5], veh[3], veh[4], veh[1], veh[2],
            "Yes", "No", "Yes", "Yes",
            "No", "No",
            "Good", "Minor scratches", "Good", "Good", "Good", "Good",
            "Half", "No", "Demo Field Agent", agent_id,
            ts(10), ts(10), ts(10),
        ))

    # ── Recovery targets (2 required)
    recovery_targets = [
        ("VIC", "XRT999", "WBAAN37080NM25791", "BMW", "5 Series", "2018", "Black", "Daniel", "Mercer"),
        ("VIC", "YRS888", "JN8AZ2KR4CT550123", "Nissan", "Patrol",  "2016", "White", "Patricia", "Forsyth"),
    ]
    rt_ids = []
    for i, (state, rego, vin, make, model, year, colour, fn, ln) in enumerate(recovery_targets):
        cur.execute("""
            INSERT INTO recovery_targets (
                ref, record_type, status, created_at, updated_at, created_by_user_id,
                assigned_agency, internal_reference, lender_reference
            ) VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            f"RT-DEMO-{i+1:04d}", "Recovery Target", "Active",
            ts(30 + i * 5), ts(30 + i * 5), admin_id,
            "SWPI Demo Agency", f"RT-DEMO-{i+1:04d}", f"LR-{i+1:06d}",
        ))
        rt_id = cur.lastrowid
        rt_ids.append(rt_id)

        cur.execute("""
            INSERT INTO recovery_target_people (
                target_id, full_legal_name, date_of_birth, driver_licence_number, licence_state
            ) VALUES (?,?,?,?,?)
        """, (rt_id, f"{fn} {ln}", "1985-06-15", f"DL{i+1:06d}VIC", "VIC"))

        cur.execute("""
            INSERT INTO recovery_target_assets (
                target_id, asset_type, make, model, year, colour, registration_number, vin
            ) VALUES (?,?,?,?,?,?,?,?)
        """, (rt_id, "Vehicle", make, model, year, colour, rego, vin))

        cur.execute("""
            INSERT INTO recovery_target_phones (target_id, phone_number, label, is_primary)
            VALUES (?,?,?,1)
        """, (rt_id, f"04{i+1:02d} 999 88{i:02d}", "Mobile"))

        rego_norm = rego.upper().replace(" ", "")
        cur.execute("""
            INSERT INTO lpr_watchlist (registration, registration_normalised, priority, reason, created_by, created_at)
            VALUES (?,?,5,?,?,?)
        """, (rego, rego_norm, f"[DEMO] Recovery target vehicle — {fn} {ln}", admin_id, ts(30 + i * 5)))

    # ── Pending review updates (2)
    for seq in (1, 2):
        jid = job_ids.get(seq)
        if jid:
            note_row = conn.execute(
                "SELECT id FROM job_field_notes WHERE job_id=? AND review_status='pending' LIMIT 1",
                (jid,)
            ).fetchone()
            if not note_row:
                cur.execute("""
                    INSERT INTO job_field_notes (job_id, created_by_user_id, note_text, created_at, review_status)
                    VALUES (?,?,?,?,'pending')
                """, (
                    jid, agent_id,
                    "Vehicle sighted in driveway. Debtor present but refused access. Update pending review.",
                    ts(1),
                ))

    # ── Overdue urgent update schedules (2)
    uu_bt_id = bt_rows.get("Urgent Update Required", bt_rows.get("Update Required", 1))
    for seq in (18, 19):
        jid = job_ids.get(seq)
        if jid:
            cur.execute("""
                INSERT INTO urgent_update_log (
                    job_id, sched_id, triggered_by_user_id, agent_user_id, triggered_at
                ) VALUES (?,?,?,?,?)
            """, (jid, 9000 + seq, admin_id, agent_id, ts(14)))

    # ── Client update request (job 1 queue item)
    jid_1 = job_ids.get(1)
    if jid_1:
        cur.execute("""
            INSERT INTO cue_items (
                job_id, visit_type, due_date, priority, status,
                assigned_user_id, instructions, created_by_user_id, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            jid_1, "Update Required",
            (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "High", "Pending", agent_id,
            "Client has requested a status update. Please contact and report back by COB today.",
            admin_id, ts(1), ts(1),
        ))

    # ── Closure request (job 17 — already repossessed)
    jid_17 = job_ids.get(17)
    if jid_17:
        cur.execute("""
            INSERT INTO cue_items (
                job_id, visit_type, due_date, priority, status,
                instructions, created_by_user_id, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            jid_17, "File Closure",
            datetime.now().strftime("%Y-%m-%d"),
            "Normal", "Pending",
            "Vehicle recovered and VIR completed. Closure request submitted — awaiting invoice approval.",
            admin_id, ts(10), ts(10),
        ))

    # ── Demo outbox pre-seeded message
    cur.execute("""
        INSERT INTO demo_outbox (msg_type, recipient, subject, body, created_at)
        VALUES (?,?,?,?,?)
    """, (
        "email", "demo.agent@axionx.demo",
        "New Job Assigned — DEMO0001",
        "A new job DEMO0001 has been assigned to you. Please attend the address by tomorrow morning.",
        ts(14),
    ))

    # ── Initial reset-log entry — records this seed run itself
    cur.execute("""
        INSERT INTO demo_reset_log (reset_at, triggered_by, role, ip_address, outcome, notes)
        VALUES (?,?,?,?,?,?)
    """, (
        now_ts(), "seed_script", "demo_admin", None, "success",
        "Initial demo database seed — baseline data created.",
    ))

    conn.commit()
    print(f"[SEED] Seeded {len(job_ids)} jobs, {len(customer_ids)} customers, "
          f"{len(client_ids)} clients, {len(rt_ids)} recovery targets.")


def main():
    parser = argparse.ArgumentParser(description="AxionX Demo DB Seeder")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate demo DB")
    args = parser.parse_args()

    if args.reset:
        for suffix in ("", "-wal", "-shm"):
            p = DEMO_DB_PATH + suffix
            if os.path.exists(p):
                os.remove(p)
                print(f"[SEED] Deleted: {p}")

    conn = _conn()
    try:
        create_schema(conn)
        seed(conn)
        print("[SEED] Demo database ready.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
