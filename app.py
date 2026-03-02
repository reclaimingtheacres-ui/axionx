from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify, Response, abort
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import csv
import json
import os
import re
import io
import mimetypes
from datetime import date, datetime
import pytz
from azure.storage.blob import BlobServiceClient, ContentSettings

_melbourne = pytz.timezone("Australia/Melbourne")

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "axion-dev-secret")
app.config["PERMANENT_SESSION_LIFETIME"] = __import__("datetime").timedelta(hours=8)

DB_PATH = "axion.db"

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf", "doc", "docx", "xls", "xlsx", "csv", "heic", "heif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Azure Blob Storage ─────────────────────────────────────────────────────────
_AZURE_CONN_STR  = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
_AZURE_CONTAINER = os.getenv("AZURE_UPLOADS_CONTAINER", "axion-uploads")

try:
    _blob_service      = BlobServiceClient.from_connection_string(_AZURE_CONN_STR) if _AZURE_CONN_STR else None
    _uploads_container = _blob_service.get_container_client(_AZURE_CONTAINER) if _blob_service else None
except Exception as _e:
    print(f"[Azure] Client init failed: {_e}")
    _blob_service = _uploads_container = None


def upload_to_blob(file_storage, blob_name: str) -> int:
    """Upload a Werkzeug FileStorage to Azure Blob. Returns file size in bytes."""
    data = file_storage.read()
    ct   = file_storage.mimetype or mimetypes.guess_type(blob_name)[0] or "application/octet-stream"
    _uploads_container.upload_blob(
        name=blob_name,
        data=data,
        overwrite=True,
        content_settings=ContentSettings(content_type=ct),
    )
    return len(data)


def delete_blob_safely(blob_name: str):
    """Delete a blob, silently ignore errors."""
    try:
        if _uploads_container:
            _uploads_container.delete_blob(blob_name)
    except Exception:
        pass
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/favicon.ico")
def favicon():
    return send_from_directory("static", "favicon.ico", mimetype="image/png")

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def add_column_if_missing(cur, table, col, coltype):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r["name"] for r in cur.fetchall()]
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
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
        updated_at TEXT NOT NULL DEFAULT ''
    )
    """)

    for col, definition in [
        ("updated_at", "TEXT NOT NULL DEFAULT ''"),
    ]:
        try:
            cur.execute(f"ALTER TABLE clients ADD COLUMN {col} {definition}")
        except Exception:
            pass

    cur.execute("""
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
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(uploaded_by_user_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS contact_phone_numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        label TEXT NOT NULL,
        phone_number TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS contact_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        label TEXT,
        email TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
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

        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,

        FOREIGN KEY(client_id) REFERENCES clients(id),
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(assigned_user_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
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

        notes TEXT,

        created_at TEXT NOT NULL,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    )
    """)

    cur.execute("""
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
        updated_at TEXT NOT NULL,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        narrative TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        photo_path TEXT,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    )
    """)

    cur.execute("""
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
        completed_at TEXT,
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(assigned_user_id) REFERENCES users(id),
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        used INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """
    )
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_user_id INTEGER,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        action TEXT NOT NULL,
        message TEXT NOT NULL,
        meta_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(actor_user_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS job_field_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        created_by_user_id INTEGER,
        note_text TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS job_note_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_field_note_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY(job_field_note_id) REFERENCES job_field_notes(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS booking_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        active INTEGER NOT NULL DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        booking_type_id INTEGER NOT NULL,
        scheduled_for TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Booked',
        notes TEXT,
        created_by_user_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(booking_type_id) REFERENCES booking_types(id),
        FOREIGN KEY(created_by_user_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        job_prefix TEXT NOT NULL,
        job_sequence INTEGER NOT NULL,
        auto_prefix_enabled INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
    )
    """)

    cur.execute("SELECT COUNT(*) c FROM system_settings")
    if cur.fetchone()["c"] == 0:
        current_prefix = datetime.now().strftime("%y%m")
        cur.execute("""
            INSERT INTO system_settings (id, job_prefix, job_sequence, auto_prefix_enabled, updated_at)
            VALUES (1, ?, 0, 1, ?)
        """, (current_prefix, now_ts()))

    for col, coltype in [
        ("lender_name",       "TEXT"),
        ("account_number",    "TEXT"),
        ("regulation_type",   "TEXT"),
        ("arrears_cents",     "INTEGER"),
        ("costs_cents",       "INTEGER"),
        ("mmp_cents",         "INTEGER"),
        ("job_due_date",      "TEXT"),
        ("payment_frequency", "TEXT"),
    ]:
        add_column_if_missing(cur, "jobs", col, coltype)

    add_column_if_missing(cur, "interactions", "photo_path", "TEXT")
    add_column_if_missing(cur, "schedules", "assigned_to_user_id", "INTEGER")
    add_column_if_missing(cur, "jobs", "bill_to_client_id", "INTEGER")
    add_column_if_missing(cur, "customers", "role", "TEXT")

    _default_booking_types = [
        "New Visit", "Re-attend", "Urgent New Visit",
        "Update Required", "Urgent Update Required",
    ]
    cur.execute("SELECT name FROM booking_types")
    existing_bt = {r["name"] for r in cur.fetchall()}
    for bt_name in _default_booking_types:
        if bt_name not in existing_bt:
            cur.execute("INSERT INTO booking_types (name) VALUES (?)", (bt_name,))

    for col, coltype in [
        ("lender_name",    "TEXT"),
        ("account_number", "TEXT"),
        ("regulation_type","TEXT"),
    ]:
        add_column_if_missing(cur, "job_items", col, coltype)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS job_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)
    _default_job_types = ["Repo/Collect", "Collect Only", "Field Call", "Process Serve"]
    cur.execute("SELECT name FROM job_types")
    existing_jt = {r["name"] for r in cur.fetchall()}
    for jt_name in _default_job_types:
        if jt_name not in existing_jt:
            cur.execute("INSERT INTO job_types (name) VALUES (?)", (jt_name,))

    cur.execute("""
        CREATE TABLE IF NOT EXISTS job_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'Primary',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE(job_id, customer_id)
        )
    """)

    cur.execute("""
        INSERT OR IGNORE INTO job_customers (job_id, customer_id, role, sort_order, created_at)
        SELECT id, customer_id, 'Primary', 0, created_at
        FROM jobs
        WHERE customer_id IS NOT NULL
    """)

    conn.commit()
    conn.close()


@app.context_processor
def inject_globals():
    return {"GOOGLE_MAPS_API_KEY": os.environ.get("GOOGLE_MAPS_API_KEY", "")}


@app.before_request
def _ensure_db():
    init_db()


# -------- Helpers --------
def now_ts():
    melb = pytz.timezone("Australia/Melbourne")
    return datetime.now(melb).strftime("%Y-%m-%dT%H:%M:%S")


def money_to_cents(s: str) -> int:
    s = (s or "").strip()
    if not s:
        return 0
    s = s.replace("$", "").replace(",", "").strip()
    if not re.match(r"^\d+(\.\d{1,2})?$", s):
        return 0
    if "." in s:
        dollars, cents = s.split(".", 1)
        cents = (cents + "00")[:2]
    else:
        dollars, cents = s, "00"
    return int(dollars) * 100 + int(cents)


def cents_to_money(cents) -> str:
    return f"${int(cents or 0) / 100:,.2f}"


def format_ddmmyyyy(d):
    if d is None:
        return ""
    if isinstance(d, str):
        try:
            d = datetime.strptime(d[:10], "%Y-%m-%d").date()
        except Exception:
            return d
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%d/%m/%Y")


def parse_interaction_datetime(date_str: str, time_str: str) -> str:
    date_str = (date_str or "").strip()
    time_str = (time_str or "").strip().upper()
    if not date_str:
        return datetime.now().isoformat(timespec="seconds")
    try:
        if time_str:
            combined = f"{date_str} {time_str}"
            dt = datetime.strptime(combined, "%d/%m/%Y %I:%M %p")
        else:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
        return dt.isoformat(timespec="seconds")
    except Exception:
        return datetime.now().isoformat(timespec="seconds")


_AUTO_ADVANCE_TYPES = {
    "attendance", "repo attempt", "card left", "neighbour interview", "note"
}

def maybe_auto_advance_status(cur, job_id: int, current_status: str,
                               event_type: str, role: str) -> bool:
    if role != "admin":
        return False
    if event_type.lower() not in _AUTO_ADVANCE_TYPES:
        return False
    if current_status != "New":
        return False
    cur.execute("UPDATE jobs SET status = 'Active' WHERE id = ?", (job_id,))
    return True


def format_interaction_dt(s: str) -> str:
    if not s:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(s[:19], fmt)
            return dt.strftime("%-d/%-m/%Y %-I:%M %p").lower()
        except Exception:
            continue
    return s


def calc_total_due_now(arrears, costs, mmp, due_date):
    arrears = float(arrears or 0)
    costs = float(costs or 0)
    mmp = float(mmp or 0)
    if isinstance(due_date, str):
        try:
            due_date = datetime.strptime(due_date[:10], "%Y-%m-%d").date()
        except Exception:
            due_date = None
    if isinstance(due_date, datetime):
        due_date = due_date.date()
    today = datetime.now(_melbourne).date()
    total = arrears + costs
    include_mmp = bool(due_date and due_date < today)
    if include_mmp:
        total += mmp
    return round(total, 2), include_mmp


app.jinja_env.globals.update(
    cents_to_money=cents_to_money,
    format_ddmmyyyy=format_ddmmyyyy,
    format_interaction_dt=format_interaction_dt,
)


def users_count():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) c FROM users")
    c = cur.fetchone()["c"]
    conn.close()
    return c


def generate_internal_job_number():
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM system_settings WHERE id = 1")
    settings = cur.fetchone()

    current_prefix = settings["job_prefix"]
    auto_enabled = settings["auto_prefix_enabled"]

    if auto_enabled:
        actual_prefix = datetime.now().strftime("%y%m")
        if actual_prefix != current_prefix:
            current_prefix = actual_prefix
            cur.execute("""
                UPDATE system_settings
                SET job_prefix = ?, job_sequence = 0, updated_at = ?
                WHERE id = 1
            """, (actual_prefix, now_ts()))
            conn.commit()

    new_sequence = settings["job_sequence"] + 1
    padded = str(new_sequence).zfill(3)

    cur.execute("""
        UPDATE system_settings
        SET job_sequence = ?, updated_at = ?
        WHERE id = 1
    """, (new_sequence, now_ts()))

    conn.commit()
    conn.close()

    return f"{current_prefix}{padded}"


def audit(entity_type, entity_id, action, message, meta=None):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO audit_log (actor_user_id, entity_type, entity_id, action, message, meta_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session.get("user_id"),
        entity_type,
        entity_id,
        action,
        message,
        json.dumps(meta) if meta else None,
        now_ts()
    ))
    conn.commit()
    conn.close()


# -------- Auth helpers --------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper


# -------- Login / Logout --------

import smtplib as _smtplib
import os as _os
from email.mime.multipart import MIMEMultipart as _MIMEMultipart
from email.mime.text import MIMEText as _MIMEText


def send_reset_email(to_addr, reset_link):
    host = _os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(_os.environ.get("SMTP_PORT", "587"))
    user = _os.environ.get("SMTP_USER", "")
    pswd = _os.environ.get("SMTP_PASS", "")
    frm  = _os.environ.get("SMTP_FROM", user)
    if not user or not pswd:
        raise RuntimeError("SMTP credentials not configured.")
    msg = _MIMEMultipart("alternative")
    msg["Subject"] = "Axion — Password Reset"
    msg["From"]    = frm
    msg["To"]      = to_addr
    txt = f"Click the link below to reset your Axion password:\n\n{reset_link}\n\nThis link expires in 1 hour."
    htm = f"""<div style="font-family:sans-serif;max-width:480px;margin:0 auto">
  <h2 style="color:#0f172a">Reset your Axion password</h2>
  <p>Click the button below to choose a new password. This link expires in <strong>1 hour</strong>.</p>
  <p><a href="{reset_link}" style="display:inline-block;background:#3b82f6;color:#fff;
     padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">Reset Password</a></p>
  <p style="color:#6b7280;font-size:13px">If you did not request this, you can safely ignore this email.</p>
  <hr style="border:none;border-top:1px solid #e5e7eb">
  <p style="color:#9ca3af;font-size:12px">Axion Field Operations Management</p>
</div>"""
    msg.attach(_MIMEText(txt, "plain"))
    msg.attach(_MIMEText(htm, "html"))
    with _smtplib.SMTP(host, port, timeout=10) as s:
        s.ehlo()
        s.starttls()
        s.login(user, pswd)
        s.sendmail(frm, to_addr, msg.as_string())


@app.get("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")


@app.post("/forgot-password")
def forgot_password_post():
    import secrets as _tok
    from datetime import timedelta as _td
    email = request.form.get("email", "").strip().lower()
    generic_msg = "If that email is registered you\u2019ll receive a reset link shortly."
    if not email:
        flash(generic_msg, "success")
        return redirect(url_for("forgot_password"))
    conn = db()
    cur  = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ? AND active = 1", (email,))
    user = cur.fetchone()
    if user:
        token   = _tok.token_urlsafe(32)
        expires = (datetime.now() + _td(hours=1)).isoformat(timespec="seconds")
        created = datetime.now().isoformat(timespec="seconds")
        cur.execute("""INSERT INTO password_reset_tokens (user_id, token, expires_at, used, created_at)
                       VALUES (?, ?, ?, 0, ?)""", (user["id"], token, expires, created))
        conn.commit()
        link = request.host_url.rstrip("/") + url_for("reset_password", token=token)
        try:
            send_reset_email(email, link)
        except Exception as e:
            import sys
            print(f"[SMTP ERROR] {e}", file=sys.stderr)
    conn.close()
    flash(generic_msg, "success")
    return redirect(url_for("forgot_password"))


@app.get("/reset-password/<token>")
def reset_password(token):
    conn = db()
    cur  = conn.cursor()
    cur.execute("""SELECT * FROM password_reset_tokens
                   WHERE token = ? AND used = 0 AND expires_at > ?""",
                (token, datetime.now().isoformat(timespec="seconds")))
    row = cur.fetchone()
    conn.close()
    if not row:
        flash("That reset link is invalid or has expired.", "danger")
        return redirect(url_for("forgot_password"))
    return render_template("reset_password.html", token=token)


@app.post("/reset-password/<token>")
def reset_password_post(token):
    conn = db()
    cur  = conn.cursor()
    cur.execute("""SELECT * FROM password_reset_tokens
                   WHERE token = ? AND used = 0 AND expires_at > ?""",
                (token, datetime.now().isoformat(timespec="seconds")))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("That reset link is invalid or has expired.", "danger")
        return redirect(url_for("forgot_password"))
    new_pw  = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    if len(new_pw) < 8:
        conn.close()
        flash("Password must be at least 8 characters.", "danger")
        return redirect(url_for("reset_password", token=token))
    if new_pw != confirm:
        conn.close()
        flash("Passwords do not match.", "danger")
        return redirect(url_for("reset_password", token=token))
    hashed = generate_password_hash(new_pw)
    cur.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, row["user_id"]))
    cur.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    flash("Password updated. Please sign in.", "success")
    return redirect(url_for("login"))


@app.get("/login")
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
    allow_signup = users_count() == 0
    return render_template("login.html", allow_signup=allow_signup)


@app.get("/signup")
def signup():
    if users_count() > 0:
        return ("Signup disabled. Ask an admin to create your account.", 403)
    return render_template("signup.html")


@app.post("/signup")
def signup_post():
    if users_count() > 0:
        return ("Signup disabled. Ask an admin to create your account.", 403)

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not full_name or not email or not password:
        flash("All fields are required.", "danger")
        return redirect(url_for("signup"))

    hashed = generate_password_hash(password)
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (full_name, email, password, role, active, created_at)
        VALUES (?, ?, ?, 'admin', 1, ?)
    """, (full_name, email, hashed, now_ts()))
    user_id = cur.lastrowid
    conn.commit()
    conn.close()

    session["user_id"] = user_id
    session["user_name"] = full_name
    session["role"] = "admin"
    flash(f"Welcome, {full_name}! Admin account created.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/login")
def login_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ? AND active = 1", (email,))
    user = cur.fetchone()
    conn.close()

    if not user or not check_password_hash(user["password"], password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    session.permanent = True
    session["user_id"] = user["id"]
    session["user_name"] = user["full_name"]
    session["role"] = user["role"]
    next_url = request.args.get("next", "").strip()
    return redirect(next_url if next_url and next_url.startswith("/") else url_for("jobs_list"))


@app.get("/logout")
def logout():
    reason = request.args.get("reason", "")
    user_id = session.get("user_id")
    user_name = session.get("user_name", "Unknown")
    if reason == "timeout" and user_id:
        audit("user", user_id, "logout", f"Session auto-expired due to inactivity: {user_name}", {})
    session.clear()
    if reason == "timeout":
        flash("Your session expired due to inactivity. Please sign in again.", "warning")
    return redirect(url_for("login"))


# -------- Home --------
@app.get("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("jobs_list"))
    return redirect(url_for("login"))



def auto_queue_schedule_alerts(cur, admin_user_id):
    """Auto-create queue items for jobs with overdue/today/tomorrow schedules."""
    import datetime as _dt
    _mel_now = datetime.now(_melbourne)
    today = _mel_now.date().isoformat()
    tomorrow = (_mel_now.date() + _dt.timedelta(days=1)).isoformat()
    now_str = _mel_now.isoformat(timespec="seconds")

    cur.execute("""
        SELECT j.id, j.display_ref, s.scheduled_for,
               date(s.scheduled_for,'localtime') AS sched_date
        FROM jobs j
        JOIN (
            SELECT job_id, MIN(scheduled_for) AS scheduled_for
            FROM schedules
            WHERE date(scheduled_for,'localtime') <= ?
            GROUP BY job_id
        ) s ON s.job_id = j.id
        WHERE j.status NOT IN ('Completed', 'Invoiced', 'New')
    """, (tomorrow,))
    candidates = cur.fetchall()

    visit_map = {
        "past":     ("Urgent: Schedule Overdue",  "Urgent"),
        "today":    ("Schedule Due Today",         "High"),
        "tomorrow": ("Schedule Due Tomorrow",      "Normal"),
    }

    for row in candidates:
        sched_date = row["sched_date"]
        if sched_date < today:
            bucket = "past"
        elif sched_date == today:
            bucket = "today"
        else:
            bucket = "tomorrow"

        visit_type, priority = visit_map[bucket]

        cur.execute("""
            SELECT id FROM cue_items
            WHERE job_id = ? AND visit_type = ?
              AND status IN ('Pending','In Progress')
        """, (row["id"], visit_type))
        if cur.fetchone():
            continue

        cur.execute("""
            INSERT INTO cue_items
              (job_id, visit_type, due_date, priority, status,
               created_by_user_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'Pending', ?, ?, ?)
        """, (row["id"], visit_type, today, priority,
              admin_user_id, now_str, now_str))

@app.get("/dashboard")
@login_required
def dashboard():
    user_id = session.get("user_id")
    role    = session.get("role")
    conn = db()
    cur  = conn.cursor()

    def jcount(where="", params=()):
        q = f"SELECT COUNT(*) AS c FROM jobs{(' WHERE ' + where) if where else ''}"
        cur.execute(q, params)
        return cur.fetchone()["c"]

    STATUS_LIST = [
        ("New",                       "new"),
        ("Active",                    "active"),
        ("Active - Phone work only",  "phone"),
        ("Suspended",                 "suspended"),
        ("Awaiting info from client", "awaiting"),
        ("Completed",                 "completed"),
        ("Invoiced",                  "invoiced"),
    ]

    def jrows(status):
        agent_subq = """
            COALESCE(u.full_name,
                (SELECT u2.full_name FROM schedules sx
                 JOIN users u2 ON u2.id = sx.assigned_to_user_id
                 WHERE sx.job_id = j.id
                 ORDER BY sx.created_at DESC LIMIT 1)
            ) AS assigned_name"""
        sched_subq = """
            (SELECT sx2.scheduled_for FROM schedules sx2
             WHERE sx2.job_id = j.id
               AND date(sx2.scheduled_for) >= date('now','localtime')
             ORDER BY sx2.scheduled_for ASC LIMIT 1) AS next_scheduled"""
        base_sel = f"""
                SELECT j.id, j.display_ref, j.status,
                       COALESCE(CASE WHEN cu.last_name IS NOT NULL THEN cu.last_name || COALESCE(' ' || cu.first_name, '') ELSE NULL END,
                                cu.company, 'No customer') AS customer_name,
                       {agent_subq},
                       {sched_subq}
                FROM jobs j
                LEFT JOIN customers cu ON cu.id = j.customer_id
                LEFT JOIN users u ON u.id = j.assigned_user_id"""
        if role == "agent":
            sql = base_sel + """
                WHERE j.status = ? AND j.assigned_user_id = ?
                ORDER BY j.updated_at DESC"""
            cur.execute(sql, (status, user_id))
        else:
            sql = base_sel + """
                WHERE j.status = ?
                ORDER BY j.updated_at DESC"""
            cur.execute(sql, (status,))
        return cur.fetchall()

    if role == "agent":
        base = "assigned_user_id = ?"
        p    = (user_id,)
        jobs_all       = jcount(base, p)
        jobs_new       = jcount(base + " AND status = 'New'",                      (user_id,))
        jobs_active    = jcount(base + " AND status = 'Active'",                   (user_id,))
        jobs_phone     = jcount(base + " AND status = 'Active - Phone work only'", (user_id,))
        jobs_suspended = jcount(base + " AND status = 'Suspended'",                (user_id,))
        jobs_awaiting  = jcount(base + " AND status = 'Awaiting info from client'",(user_id,))
        jobs_completed = jcount(base + " AND status = 'Completed'",                (user_id,))
        jobs_invoiced  = jcount(base + " AND status = 'Invoiced'",                 (user_id,))
    else:
        jobs_all       = jcount()
        jobs_new       = jcount("status = 'New'")
        jobs_active    = jcount("status = 'Active'")
        jobs_phone     = jcount("status = 'Active - Phone work only'")
        jobs_suspended = jcount("status = 'Suspended'")
        jobs_awaiting  = jcount("status = 'Awaiting info from client'")
        jobs_completed = jcount("status = 'Completed'")
        jobs_invoiced  = jcount("status = 'Invoiced'")

    rows_by_status = {status: jrows(status) for status, _ in STATUS_LIST}

    # Auto-flag overdue / today / tomorrow schedules into the job queue
    _admin_id = user_id if role == "admin" else None
    if _admin_id:
        auto_queue_schedule_alerts(cur, _admin_id)
        conn.commit()

    conn.close()
    from datetime import timedelta as _td
    _today = datetime.now().date()
    return render_template("index.html",
        jobs_all=jobs_all,
        jobs_new=jobs_new,       jobs_active=jobs_active,
        jobs_phone=jobs_phone,   jobs_suspended=jobs_suspended,
        jobs_awaiting=jobs_awaiting, jobs_completed=jobs_completed,
        jobs_invoiced=jobs_invoiced,
        rows_by_status=rows_by_status,
        status_list=STATUS_LIST,
        today_iso=_today.isoformat(),
        tomorrow_iso=(_today + _td(days=1)).isoformat())



@app.get("/jobs")
@login_required
def jobs_list():
    status = request.args.get("status", "").strip()
    q = request.args.get("q", "").strip()

    user_id = session.get("user_id")
    role = session.get("role")

    conn = db()
    cur = conn.cursor()

    sql = """
    SELECT j.*,
           c.name AS client_name,
           (cu.first_name || ' ' || cu.last_name) AS customer_name,
           (SELECT ji.reg FROM job_items ji WHERE ji.job_id = j.id AND ji.item_type = 'vehicle' LIMIT 1) AS asset_reg,
           u.full_name AS assigned_name,
           (SELECT s.scheduled_for FROM schedules s
            WHERE s.job_id = j.id AND s.status NOT IN ('Completed', 'Cancelled')
              AND s.scheduled_for >= datetime('now')
            ORDER BY s.scheduled_for ASC LIMIT 1) AS next_scheduled
    FROM jobs j
    LEFT JOIN clients c ON c.id = j.client_id
    LEFT JOIN customers cu ON cu.id = j.customer_id
    LEFT JOIN users u ON u.id = j.assigned_user_id
    WHERE 1=1
    """
    params = []

    if role == "agent":
        sql += " AND j.assigned_user_id = ?"
        params.append(user_id)

    if status:
        if status == "Active":
            sql += " AND j.status LIKE 'Active%'"
        else:
            sql += " AND j.status = ?"
            params.append(status)

    if q:
        sql += """
         AND (
           j.internal_job_number LIKE ? OR
           j.client_reference     LIKE ? OR
           j.display_ref          LIKE ? OR
           j.description          LIKE ? OR
           j.job_address          LIKE ? OR
           cu.first_name          LIKE ? OR
           cu.last_name           LIKE ? OR
           cu.company             LIKE ? OR
           c.name                 LIKE ? OR
           EXISTS (
             SELECT 1 FROM job_items ji
             WHERE ji.job_id = j.id
               AND (ji.reg LIKE ? OR ji.vin LIKE ? OR ji.description LIKE ?)
           )
         )"""
        like = f"%{q}%"
        params.extend([like] * 12)

    sql += " ORDER BY CASE WHEN j.status = 'Invoiced' THEN 1 ELSE 0 END, CASE WHEN next_scheduled IS NULL THEN 1 ELSE 0 END, next_scheduled ASC, j.updated_at DESC"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    statuses = [
        "New",
        "Active",
        "Active - Phone work only",
        "Suspended",
        "Awaiting info from client",
        "Completed",
        "Invoiced"
    ]

    return render_template("jobs.html", jobs=rows, statuses=statuses, status=status, q=q)


@app.get("/jobs/new")
@login_required
@admin_required
def job_new():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM clients ORDER BY name")
    clients = cur.fetchall()
    cur.execute("SELECT id, first_name, last_name, company, address FROM customers ORDER BY last_name, first_name")
    customers = cur.fetchall()
    cur.execute("SELECT id, full_name FROM users WHERE active = 1 ORDER BY full_name")
    users = cur.fetchall()
    cur.execute("SELECT * FROM system_settings WHERE id = 1")
    settings = cur.fetchone()

    new_client_id   = request.args.get("new_client_id",   type=int)
    new_customer_id = request.args.get("new_customer_id", type=int)
    new_user_id     = request.args.get("new_user_id",     type=int)

    prefill_customer_address = ""
    prefill_client_reference = request.args.get("client_reference", "")
    if new_customer_id:
        cur.execute("SELECT address FROM customers WHERE id = ?", (new_customer_id,))
        row = cur.fetchone()
        if row:
            prefill_customer_address = row["address"] or ""

    cur.execute("SELECT id, name FROM job_types WHERE active = 1 ORDER BY name")
    job_types = cur.fetchall()
    cur.execute("SELECT DISTINCT lender_name FROM jobs WHERE lender_name IS NOT NULL ORDER BY lender_name")
    known_lenders = [r["lender_name"] for r in cur.fetchall()]
    conn.close()

    next_number = f"{settings['job_prefix']}{str(settings['job_sequence'] + 1).zfill(3)}"

    visit_types = ["New Visit", "Re-attend", "First Update", "Urgent Update", "Phone Follow-up", "Locate Only"]
    statuses = ["New", "Active", "Active - Phone work only", "Suspended", "Awaiting info from client", "Completed", "Invoiced"]
    priorities = ["Low", "Normal", "High", "Urgent"]

    return render_template("job_new.html", clients=clients, customers=customers,
                           users=users, visit_types=visit_types, job_types=job_types,
                           statuses=statuses, priorities=priorities,
                           next_number=next_number,
                           new_client_id=new_client_id,
                           new_customer_id=new_customer_id,
                           new_user_id=new_user_id,
                           prefill_customer_address=prefill_customer_address,
                           prefill_client_reference=prefill_client_reference,
                           known_lenders=known_lenders)


@app.post("/jobs/new")
@login_required
@admin_required
def job_create():
    internal_job_number = generate_internal_job_number()
    client_reference = request.form.get("client_reference", "").strip()
    client_id = request.form.get("client_id") or None
    customer_id = request.form.get("customer_id") or None
    bill_to_client_id = request.form.get("bill_to_client_id") or None
    assigned_user_id = request.form.get("assigned_user_id") or None
    job_type = request.form.get("job_type", "Field Call").strip()
    visit_type = request.form.get("visit_type", "New Visit").strip()
    status = request.form.get("status", "New").strip()
    priority = request.form.get("priority", "Normal").strip()
    job_address = request.form.get("job_address", "").strip()
    description = request.form.get("description", "").strip()
    lender_name = request.form.get("lender_name", "").strip()
    account_number = request.form.get("account_number", "").strip()
    regulation_type = request.form.get("regulation_type", "").strip()
    arrears_cents = money_to_cents(request.form.get("arrears"))
    costs_cents = money_to_cents(request.form.get("costs"))
    mmp_cents = money_to_cents(request.form.get("mmp"))
    job_due_date = request.form.get("job_due_date", "").strip() or None

    display_ref = internal_job_number
    if client_reference:
        display_ref = f"{internal_job_number} ({client_reference})"

    now = datetime.now().isoformat(timespec="seconds")

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO jobs (
            internal_job_number, client_reference, display_ref,
            client_id, customer_id, bill_to_client_id, assigned_user_id,
            job_type, visit_type, status, priority,
            job_address, description,
            lender_name, account_number, regulation_type,
            arrears_cents, costs_cents, mmp_cents, job_due_date,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        internal_job_number, client_reference or None, display_ref,
        client_id, customer_id, bill_to_client_id, assigned_user_id,
        job_type, visit_type, status, priority,
        job_address, description,
        lender_name or None, account_number or None, regulation_type or None,
        arrears_cents or None, costs_cents or None, mmp_cents or None, job_due_date,
        now, now
    ))
    job_id = cur.lastrowid

    if customer_id:
        cur.execute("""
            INSERT OR IGNORE INTO job_customers (job_id, customer_id, role, sort_order, created_at)
            VALUES (?, ?, 'Primary', 0, ?)
        """, (job_id, customer_id, now))

    cur.execute("""
        INSERT INTO interactions (job_id, event_type, narrative, occurred_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, "System", f"Job created: {display_ref}. Status '{status}'. Visit type '{visit_type}'.", now, now))

    asset_types   = request.form.getlist("asset_type[]")
    descs         = request.form.getlist("asset_description[]")
    regos         = request.form.getlist("asset_rego[]")
    vins          = request.form.getlist("asset_vin[]")
    years         = request.form.getlist("asset_year[]")
    makes         = request.form.getlist("asset_make[]")
    models        = request.form.getlist("asset_model[]")
    addresses     = request.form.getlist("asset_address[]")
    serials       = request.form.getlist("asset_serial[]")
    asset_notes   = request.form.getlist("asset_notes[]")

    for i in range(len(asset_types)):
        a_type  = (asset_types[i]  or "").strip()
        a_desc  = (descs[i]        or "").strip()
        a_rego  = (regos[i]        or "").strip()
        a_vin   = (vins[i]         or "").strip()
        a_year  = (years[i]        or "").strip()
        a_make  = (makes[i]        or "").strip()
        a_model = (models[i]       or "").strip()
        a_addr  = (addresses[i]    or "").strip()
        a_ser   = (serials[i]      or "").strip()
        a_note  = (asset_notes[i]  or "").strip()
        if not any([a_desc, a_rego, a_vin, a_addr, a_ser, a_note, a_make, a_model, a_year]):
            continue
        cur.execute("""
            INSERT INTO job_items
            (job_id, item_type, description, reg, vin, make, model, year, property_address, serial_number, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, (a_type or "other").lower(),
              a_desc or None, a_rego or None, a_vin or None, a_make or None, a_model or None, a_year or None,
              a_addr or None, a_ser or None, a_note or None, now))

    conn.commit()
    conn.close()

    flash("Job created.", "success")
    return redirect(url_for("index"))


@app.get("/jobs/<int:job_id>")
@login_required
def job_detail(job_id: int):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT j.*,
           c.name AS client_name, c.phone AS client_phone, c.email AS client_email, c.address AS client_address,
           (cu.first_name || ' ' || cu.last_name) AS customer_name, cu.company AS customer_company, cu.email AS customer_email, cu.dob AS customer_dob, cu.address AS customer_address,
           u.full_name AS assigned_name,
           btc.name AS bill_to_client_name
    FROM jobs j
    LEFT JOIN clients c ON c.id = j.client_id
    LEFT JOIN customers cu ON cu.id = j.customer_id
    LEFT JOIN users u ON u.id = j.assigned_user_id
    LEFT JOIN clients btc ON btc.id = j.bill_to_client_id
    WHERE j.id = ?
    """, (job_id,))
    job = cur.fetchone()
    if not job:
        conn.close()
        return ("Not found", 404)

    job = dict(job)
    total_dollars, include_mmp = calc_total_due_now(
        (job.get("arrears_cents") or 0) / 100,
        (job.get("costs_cents") or 0) / 100,
        (job.get("mmp_cents") or 0) / 100,
        job.get("job_due_date")
    )
    job["due_date_display"] = format_ddmmyyyy(job.get("job_due_date"))
    job["total_due_now_cents"] = int(round(total_dollars * 100))
    job["mmp_included_in_total"] = include_mmp

    role = session.get("role")
    user_id = session.get("user_id")
    if role == "agent" and job["assigned_user_id"] != user_id:
        conn.close()
        flash("You do not have access to that job.", "danger")
        return redirect(url_for("jobs_list"))

    cur.execute("""
    SELECT * FROM interactions
    WHERE job_id = ?
    ORDER BY occurred_at DESC, id DESC
    """, (job_id,))
    interactions = cur.fetchall()

    cur.execute("""
        SELECT phone_number, label FROM contact_phone_numbers
        WHERE entity_type = 'customer' AND entity_id = ? ORDER BY id LIMIT 1
    """, (job.get("customer_id"),))
    cphone_row = cur.fetchone()
    job["customer_phone"] = cphone_row["phone_number"] if cphone_row else None
    job["customer_phone_label"] = cphone_row["label"] if cphone_row else None

    cur.execute("SELECT * FROM job_items WHERE job_id = ? ORDER BY id", (job_id,))
    job_items = cur.fetchall()

    cur.execute("SELECT id, full_name FROM users WHERE active = 1 ORDER BY full_name")
    users = cur.fetchall()

    cur.execute("""
        SELECT fn.*, u.full_name author_name
        FROM job_field_notes fn
        LEFT JOIN users u ON u.id = fn.created_by_user_id
        WHERE fn.job_id = ?
        ORDER BY fn.created_at DESC
    """, (job_id,))
    raw_notes = cur.fetchall()

    field_notes = []
    for note in raw_notes:
        cur.execute("SELECT * FROM job_note_files WHERE job_field_note_id = ?", (note["id"],))
        files = cur.fetchall()
        field_notes.append({"note": note, "files": files})

    cur.execute("SELECT * FROM booking_types WHERE active = 1 ORDER BY name")
    booking_types = cur.fetchall()

    cur.execute("""
        SELECT s.*, bt.name booking_type_name, u.full_name assigned_to_name
        FROM schedules s
        JOIN booking_types bt ON bt.id = s.booking_type_id
        LEFT JOIN users u ON u.id = s.assigned_to_user_id
        WHERE s.job_id = ?
        ORDER BY s.scheduled_for ASC
    """, (job_id,))
    schedules = cur.fetchall()

    cur.execute("""
        SELECT d.*, u.full_name AS uploaded_by
        FROM job_documents d
        LEFT JOIN users u ON u.id = d.uploaded_by_user_id
        WHERE d.job_id = ?
        ORDER BY d.id DESC
    """, (job_id,))
    documents = cur.fetchall()

    cur.execute("""
        SELECT jc.id AS jc_id, jc.role, jc.sort_order,
               cu.id AS customer_id, cu.first_name, cu.last_name, cu.company,
               cu.email, cu.address
        FROM job_customers jc
        JOIN customers cu ON cu.id = jc.customer_id
        WHERE jc.job_id = ?
        ORDER BY jc.sort_order, jc.id
    """, (job_id,))
    job_linked_customers = cur.fetchall()

    linked_ids = [r["customer_id"] for r in job_linked_customers]
    if linked_ids:
        placeholders = ",".join("?" * len(linked_ids))
        cur.execute(f"SELECT id, first_name, last_name, company FROM customers WHERE id NOT IN ({placeholders}) ORDER BY last_name, first_name", linked_ids)
    else:
        cur.execute("SELECT id, first_name, last_name, company FROM customers ORDER BY last_name, first_name")
    all_customers = cur.fetchall()

    conn.close()

    statuses = ["New", "Active", "Active - Phone work only", "Suspended", "Awaiting info from client", "Completed", "Invoiced"]
    visit_types = ["New Visit", "Re-attend", "First Update", "Urgent Update", "Phone Follow-up", "Locate Only"]
    item_types = ["vehicle", "property", "equipment", "other"]
    doc_types = ["Instructions", "PPSR", "Contract", "Invoice", "Authority", "Form", "Other"]
    customer_roles = ["Primary", "Director", "Guarantor", "Borrower", "Spouse", "Other"]

    return render_template("job_detail.html", job=job, interactions=interactions,
                           job_items=job_items, item_types=item_types,
                           statuses=statuses, visit_types=visit_types, users=users,
                           field_notes=field_notes, documents=documents,
                           doc_types=doc_types, booking_types=booking_types,
                           schedules=schedules,
                           job_linked_customers=job_linked_customers,
                           all_customers=all_customers,
                           customer_roles=customer_roles)


@app.post("/jobs/<int:job_id>/customers/add")
@login_required
@admin_required
def job_customer_add(job_id: int):
    customer_id = request.form.get("customer_id") or None
    role = request.form.get("role", "Primary").strip()
    if not customer_id:
        flash("Please select a customer.", "warning")
        return redirect(url_for("job_detail", job_id=job_id))
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT MAX(sort_order) FROM job_customers WHERE job_id = ?", (job_id,))
    row = cur.fetchone()
    next_order = (row[0] or 0) + 1
    try:
        cur.execute("""
            INSERT INTO job_customers (job_id, customer_id, role, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, int(customer_id), role, next_order, now_ts()))
        conn.commit()
        flash("Customer added to job.", "success")
    except Exception:
        flash("That customer is already linked to this job.", "warning")
    conn.close()
    return redirect(url_for("job_detail", job_id=job_id))


@app.post("/jobs/<int:job_id>/customers/<int:jc_id>/remove")
@login_required
@admin_required
def job_customer_remove(job_id: int, jc_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM job_customers WHERE job_id = ?", (job_id,))
    count = cur.fetchone()[0]
    if count <= 1:
        conn.close()
        flash("Cannot remove the only customer on this job.", "warning")
        return redirect(url_for("job_detail", job_id=job_id))
    cur.execute("DELETE FROM job_customers WHERE id = ? AND job_id = ?", (jc_id, job_id))
    conn.commit()
    conn.close()
    flash("Customer removed from job.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.post("/jobs/<int:job_id>/schedule")
@login_required
@admin_required
def add_schedule(job_id: int):
    date_str   = request.form.get("schedule_date", "").strip()
    time_str   = request.form.get("schedule_time", "").strip()
    bt_id      = request.form.get("booking_type_id", "").strip()
    notes      = request.form.get("notes", "").strip() or None
    caller_id  = session.get("user_id")
    caller_role = session.get("role", "")

    if caller_role == "admin":
        assigned_to = request.form.get("assigned_to_user_id", "").strip() or None
        if assigned_to:
            assigned_to = int(assigned_to)
    else:
        assigned_to = caller_id

    if not date_str or not time_str or not bt_id:
        flash("Date, time and booking type are required.", "danger")
        return redirect(url_for("job_detail", job_id=job_id))

    try:
        dt_str = parse_interaction_datetime(date_str, time_str)
    except Exception:
        flash("Invalid date or time format.", "danger")
        return redirect(url_for("job_detail", job_id=job_id))

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM booking_types WHERE id = ?", (int(bt_id),))
    bt_row = cur.fetchone()
    bt_status = bt_row["name"] if bt_row else "Active"
    cur.execute("""
        INSERT INTO schedules (job_id, booking_type_id, scheduled_for, status, notes,
                               assigned_to_user_id, created_by_user_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (job_id, int(bt_id), dt_str, bt_status, notes, assigned_to, caller_id, now_ts()))
    conn.commit()
    conn.close()

    flash("Booking added.", "success")
    return redirect(url_for("job_detail", job_id=job_id))




@app.post("/jobs/<int:job_id>/activate")
@login_required
@admin_required
def job_activate(job_id):
    new_status  = request.form.get("new_status", "").strip()
    date_str    = request.form.get("schedule_date", "").strip()
    time_str    = request.form.get("schedule_time", "").strip()
    bt_id       = request.form.get("booking_type_id", "").strip()
    notes       = request.form.get("notes", "").strip() or None
    assigned_to = request.form.get("assigned_to_user_id", "").strip() or None
    caller_id   = session.get("user_id")
    now         = datetime.now().isoformat(timespec="seconds")

    allowed = ["Active", "Active - Phone work only", "Suspended", "Awaiting info from client"]
    if new_status not in allowed:
        flash("Invalid status.", "danger")
        return redirect(url_for("job_detail", job_id=job_id))

    conn = db()
    cur  = conn.cursor()

    cur.execute("UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?", (new_status, now, job_id))
    cur.execute("""INSERT INTO interactions (job_id, event_type, narrative, occurred_at, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (job_id, "Status Update", f"Status changed to '{new_status}'.", now, now))

    if date_str and time_str and bt_id:
        try:
            dt_str = parse_interaction_datetime(date_str, time_str)
            cur.execute("SELECT name FROM booking_types WHERE id = ?", (int(bt_id),))
            bt_row = cur.fetchone()
            bt_status = bt_row["name"] if bt_row else new_status
            assigned_int = int(assigned_to) if assigned_to else None
            cur.execute("""INSERT INTO schedules
                           (job_id, booking_type_id, scheduled_for, status, notes,
                            assigned_to_user_id, created_by_user_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (job_id, int(bt_id), dt_str, bt_status, notes,
                         assigned_int, caller_id, now_ts()))
        except Exception:
            flash("Schedule date/time invalid — status updated but no schedule created.", "warning")

    conn.commit()
    conn.close()
    flash("Job updated.", "success")
    return redirect(url_for("job_detail", job_id=job_id))

@app.get("/schedule")
@login_required
def schedule_index():
    from datetime import timedelta
    now    = datetime.now()
    horizon = now + timedelta(days=30)
    now_str = now.isoformat(timespec="seconds")
    hor_str = horizon.isoformat(timespec="seconds")

    conn = db()
    cur  = conn.cursor()
    caller_id   = session.get("user_id")
    caller_role = session.get("role", "")

    if caller_role == "admin":
        cur.execute("""
            SELECT s.*, bt.name booking_type_name,
                   j.internal_job_number, j.client_reference, j.display_ref, j.id job_id,
                   u.full_name assigned_to_name
            FROM schedules s
            JOIN booking_types bt ON bt.id = s.booking_type_id
            JOIN jobs j ON j.id = s.job_id
            LEFT JOIN users u ON u.id = s.assigned_to_user_id
            WHERE s.status NOT IN ('Completed', 'Cancelled')
              AND s.scheduled_for >= ?
              AND s.scheduled_for <= ?
            ORDER BY s.scheduled_for ASC
        """, (now_str, hor_str))
    else:
        cur.execute("""
            SELECT s.*, bt.name booking_type_name,
                   j.internal_job_number, j.client_reference, j.display_ref, j.id job_id,
                   u.full_name assigned_to_name
            FROM schedules s
            JOIN booking_types bt ON bt.id = s.booking_type_id
            JOIN jobs j ON j.id = s.job_id
            LEFT JOIN users u ON u.id = s.assigned_to_user_id
            WHERE s.status NOT IN ('Completed', 'Cancelled')
              AND s.assigned_to_user_id = ?
              AND s.scheduled_for >= ?
              AND s.scheduled_for <= ?
            ORDER BY s.scheduled_for ASC
        """, (caller_id, now_str, hor_str))

    bookings = cur.fetchall()
    conn.close()
    return render_template("schedule/index.html", bookings=bookings,
                           is_admin=(caller_role == "admin"))


@app.post("/booking-type")
@login_required
@admin_required
def add_booking_type():
    name = request.form.get("new_booking_type", "").strip()
    if name:
        conn = db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO booking_types (name) VALUES (?)", (name,))
            conn.commit()
            flash(f"Booking type '{name}' added.", "success")
        except Exception:
            flash("That booking type already exists.", "warning")
        finally:
            conn.close()
    referrer = request.referrer or url_for("jobs")
    return redirect(referrer)




@app.post("/booking-type/ajax")
@login_required
@admin_required
def add_booking_type_ajax():
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Name is required."})
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO booking_types (name, active) VALUES (?, 1)", (name,))
        new_id = cur.lastrowid
        conn.commit()
    except Exception:
        conn.close()
        return jsonify({"ok": False, "error": "That booking type already exists."})
    conn.close()
    return jsonify({"ok": True, "id": new_id, "name": name})



@app.post("/booking-type/delete")
@login_required
@admin_required
def booking_type_delete():
    ids = request.form.getlist("bt_ids")
    if not ids:
        flash("No booking types selected.", "warning")
        return redirect(url_for("admin_settings"))
    conn = db()
    cur = conn.cursor()
    deleted, blocked = [], []
    for bt_id in ids:
        try:
            bt_id = int(bt_id)
        except ValueError:
            continue
        cur.execute("SELECT name FROM booking_types WHERE id = ?", (bt_id,))
        row = cur.fetchone()
        if not row:
            continue
        name = row["name"]
        cur.execute("SELECT COUNT(*) cnt FROM schedules WHERE booking_type_id = ?", (bt_id,))
        count = cur.fetchone()["cnt"]
        if count > 0:
            blocked.append(f"'{name}' ({count} schedule{'s' if count != 1 else ''})")
        else:
            cur.execute("DELETE FROM booking_types WHERE id = ?", (bt_id,))
            deleted.append(name)
    conn.commit()
    conn.close()
    if deleted:
        flash(f"Deleted: {', '.join(deleted)}.", "success")
    if blocked:
        flash(f"Cannot delete — booking type(s) with existing schedules: {', '.join(blocked)}.", "warning")
    return redirect(url_for("admin_settings"))

@app.post("/job-type")
@login_required
@admin_required
def add_job_type():
    name = request.form.get("new_job_type", "").strip()
    if name:
        conn = db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO job_types (name) VALUES (?)", (name,))
            conn.commit()
            flash(f"Job type '{name}' added.", "success")
        except Exception:
            flash("That job type already exists.", "warning")
        finally:
            conn.close()
    referrer = request.referrer or url_for("job_new")
    return redirect(referrer)


@app.post("/jobs/<int:job_id>/schedule/<int:sched_id>/status")
@login_required
@admin_required
def update_schedule_status(job_id: int, sched_id: int):
    new_status = request.form.get("status", "").strip()
    allowed = {"Completed", "Cancelled"}
    if new_status not in allowed:
        flash("Invalid status.", "danger")
        return redirect(url_for("job_detail", job_id=job_id))
    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE schedules SET status = ? WHERE id = ? AND job_id = ?",
                (new_status, sched_id, job_id))
    conn.commit()
    conn.close()
    flash("Booking updated.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.post("/jobs/<int:job_id>/delete")
@login_required
@admin_required
def delete_job(job_id: int):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM job_field_notes WHERE job_id = ?", (job_id,))
    note_ids = [r["id"] for r in cur.fetchall()]
    for nid in note_ids:
        cur.execute("SELECT filename, filepath FROM job_note_files WHERE job_field_note_id = ?", (nid,))
        for f in cur.fetchall():
            delete_blob_safely(f["filename"])
            try: os.remove(f["filepath"])
            except OSError: pass
        cur.execute("DELETE FROM job_note_files WHERE job_field_note_id = ?", (nid,))
    cur.execute("DELETE FROM job_field_notes WHERE job_id = ?", (job_id,))

    cur.execute("SELECT stored_filename, filepath FROM job_documents WHERE job_id = ?", (job_id,))
    for f in cur.fetchall():
        delete_blob_safely(f["stored_filename"])
        try: os.remove(f["filepath"])
        except OSError: pass
    cur.execute("DELETE FROM job_documents WHERE job_id = ?", (job_id,))

    for tbl in ("job_items", "job_assets", "interactions", "cue_items"):
        cur.execute(f"DELETE FROM {tbl} WHERE job_id = ?", (job_id,))

    cur.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()

    audit("job", job_id, "delete", "Job deleted", {})
    flash("Job deleted.", "success")
    return redirect(url_for("jobs"))


@app.post("/jobs/<int:job_id>/status")
@login_required
@admin_required
def job_status_update(job_id: int):
    status = request.form.get("status", "").strip()
    allowed = ["New", "Active", "Active - Phone work only", "Suspended",
               "Awaiting info from client", "Completed", "Invoiced"]
    if status not in allowed:
        flash("Invalid status.", "danger")
        return redirect(url_for("jobs_list"))
    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, job_id))
    cur.execute("""
        INSERT INTO interactions (job_id, event_type, narrative, occurred_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, "Status Update", f"Status changed to '{status}'.", now, now))
    if status in ("Completed", "Invoiced"):
        cur.execute("UPDATE jobs SET assigned_user_id = NULL, updated_at = ? WHERE id = ?",
                    (now, job_id))
        cur.execute("""
            UPDATE schedules SET status = 'Cancelled'
            WHERE job_id = ? AND status NOT IN ('Completed', 'Cancelled')
        """, (job_id,))
        cur.execute("""
            INSERT INTO interactions (job_id, event_type, narrative, occurred_at, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, "System",
                f"Agent unassigned and pending schedules cancelled — job marked '{status}'.",
                now, now))
    conn.commit()
    conn.close()
    return redirect(url_for("job_detail", job_id=job_id))


@app.post("/jobs/<int:job_id>/update")
@login_required
@admin_required
def job_update(job_id: int):
    status = request.form.get("status", "").strip()
    visit_type = request.form.get("visit_type", "").strip()
    assigned_user_id = request.form.get("assigned_user_id") or None
    now = datetime.now().isoformat(timespec="seconds")

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET status = ?, visit_type = ?, assigned_user_id = ?, updated_at = ? WHERE id = ?",
                (status, visit_type, assigned_user_id, now, job_id))

    cur.execute("""
        INSERT INTO interactions (job_id, event_type, narrative, occurred_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, "Status/Visit Update", f"Status set to '{status}'. Visit type set to '{visit_type}'.", now, now))

    if status in ("Completed", "Invoiced"):
        cur.execute("UPDATE jobs SET assigned_user_id = NULL, updated_at = ? WHERE id = ?",
                    (now, job_id))
        cur.execute("""
            UPDATE schedules SET status = 'Cancelled'
            WHERE job_id = ? AND status NOT IN ('Completed', 'Cancelled')
        """, (job_id,))
        cur.execute("""
            INSERT INTO interactions (job_id, event_type, narrative, occurred_at, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, "System",
                f"Agent unassigned and pending schedules cancelled — job marked '{status}'.",
                now, now))

    conn.commit()
    conn.close()
    flash("Job updated.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.post("/jobs/<int:job_id>/lender")
@login_required
@admin_required
def job_lender_update(job_id: int):
    lender_name     = request.form.get("lender_name", "").strip()
    account_number  = request.form.get("account_number", "").strip()
    regulation_type    = request.form.get("regulation_type", "").strip()
    arrears_cents      = money_to_cents(request.form.get("arrears", ""))
    costs_cents        = money_to_cents(request.form.get("costs", ""))
    mmp_cents          = money_to_cents(request.form.get("mmp", ""))
    job_due_date       = request.form.get("job_due_date", "").strip() or None
    payment_frequency  = request.form.get("payment_frequency", "").strip() or None
    conn = db()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE jobs SET lender_name=?, account_number=?, regulation_type=?,
        arrears_cents=?, costs_cents=?, mmp_cents=?, job_due_date=?,
        payment_frequency=?, updated_at=? WHERE id=?
    """, (lender_name or None, account_number or None, regulation_type or None,
          arrears_cents or None, costs_cents or None, mmp_cents or None,
          job_due_date, payment_frequency, now_ts(), job_id))
    conn.commit()
    conn.close()
    flash("Lender details updated.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.post("/jobs/<int:job_id>/interactions/new")
@login_required
@admin_required
def interaction_add(job_id: int):
    event_type = request.form.get("event_type", "Note").strip()
    narrative = request.form.get("narrative", "").strip()
    interaction_date = request.form.get("interaction_date", "").strip()
    interaction_time = request.form.get("interaction_time", "").strip()

    if not narrative:
        flash("Narrative text is required.", "danger")
        return redirect(url_for("job_detail", job_id=job_id))

    occurred_at = parse_interaction_datetime(interaction_date, interaction_time)

    photo_path = None
    photo = request.files.get("attendance_photo")
    if photo and photo.filename:
        ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
        if ext in {"png", "jpg", "jpeg", "webp", "heic"}:
            stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(photo.filename)}"
            blob_name   = f"interactions/{job_id}/{stored_name}"
            upload_to_blob(photo, blob_name)
            photo_path = blob_name

    now = datetime.now().isoformat(timespec="seconds")

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
    job_row = cur.fetchone()
    current_status = job_row["status"] if job_row else ""

    cur.execute("""
        INSERT INTO interactions (job_id, event_type, narrative, occurred_at, created_at, photo_path)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (job_id, event_type, narrative, occurred_at, now, photo_path))

    advanced = maybe_auto_advance_status(
        cur, job_id, current_status, event_type, session.get("role", "")
    )
    cur.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (now, job_id))
    conn.commit()
    conn.close()

    if advanced:
        flash("Interaction added. Job status automatically set to Active.", "success")
    else:
        flash("Interaction added.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


# -------- Clients --------
@app.get("/clients")
@login_required
def clients_list():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return render_template("clients.html", clients=rows)



@app.post("/clients/delete")
@login_required
@admin_required
def clients_delete():
    ids = request.form.getlist("client_ids")
    if not ids:
        flash("No clients selected.", "warning")
        return redirect(url_for("clients_list"))

    conn = db()
    cur = conn.cursor()
    deleted, blocked = [], []
    for cid in ids:
        try:
            cid = int(cid)
        except ValueError:
            continue
        cur.execute("SELECT name FROM clients WHERE id = ?", (cid,))
        row = cur.fetchone()
        if not row:
            continue
        name = row["name"]
        cur.execute(
            "SELECT COUNT(*) cnt FROM jobs WHERE client_id = ? OR bill_to_client_id = ?",
            (cid, cid)
        )
        job_count = cur.fetchone()["cnt"]
        if job_count > 0:
            blocked.append(f"'{name}' ({job_count} job{'s' if job_count != 1 else ''})")
        else:
            cur.execute("DELETE FROM clients WHERE id = ?", (cid,))
            deleted.append(name)
    conn.commit()
    conn.close()

    if deleted:
        flash(f"Deleted: {', '.join(deleted)}.", "success")
    if blocked:
        flash(
            f"Could not delete — client(s) with existing jobs: {', '.join(blocked)}.",
            "warning"
        )
    return redirect(url_for("clients_list"))

@app.get("/clients/new")
@login_required
@admin_required
def client_new():
    next_url = request.args.get("next", "")
    return render_template("client_new.html", next_url=next_url)


@app.post("/clients/new")
@login_required
@admin_required
def client_create():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    notes = request.form.get("notes", "").strip()
    if not name:
        flash("Client name is required.", "danger")
        return redirect(url_for("client_new"))

    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO clients (name, phone, email, address, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, phone, email, address, notes, now))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    flash("Client created.", "success")
    next_url = request.form.get("next_url", "")
    if next_url:
        return redirect(f"{next_url}?new_client_id={new_id}")
    return redirect(url_for("clients_list"))



@app.get("/clients/new-popup")
@login_required
@admin_required
def client_new_popup():
    return render_template("partials/client_popup.html")


@app.post("/clients/new-popup")
@login_required
@admin_required
def client_create_popup():
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Client name is required."})
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO clients (name, phone, email, created_at) VALUES (?, ?, ?, ?)",
        (name, phone or None, email or None, now)
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": new_id, "label": name})


@app.get("/customers/new-popup")
@login_required
@admin_required
def customer_new_popup():
    return render_template("partials/customer_popup.html")


@app.post("/customers/new-popup")
@login_required
@admin_required
def customer_create_popup():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    if not first_name or not last_name:
        return jsonify({"ok": False, "error": "First and last name are required."})
    company = request.form.get("company", "").strip()
    address = request.form.get("address", "").strip()

    phone_labels  = request.form.getlist("phone_label[]")
    phone_numbers = request.form.getlist("phone_number[]")
    email_labels  = request.form.getlist("email_label[]")
    email_addrs   = request.form.getlist("email_address[]")

    phones = [(lbl.strip(), num.strip()) for lbl, num in zip(phone_labels, phone_numbers) if num.strip()]
    emails = [(lbl.strip(), addr.strip()) for lbl, addr in zip(email_labels, email_addrs) if addr.strip()]

    first_email = emails[0][1] if emails else None

    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO customers (first_name, last_name, company, email, address, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (first_name, last_name, company or None, first_email, address or None, now, now))
    new_id = cur.lastrowid

    for lbl, num in phones:
        cur.execute("""
            INSERT INTO contact_phone_numbers (entity_type, entity_id, label, phone_number, created_at)
            VALUES ('customer', ?, ?, ?, ?)
        """, (new_id, lbl or "Mobile", num, now))

    for lbl, addr in emails:
        cur.execute("""
            INSERT INTO contact_emails (entity_type, entity_id, label, email, created_at)
            VALUES ('customer', ?, ?, ?, ?)
        """, (new_id, lbl or "Email", addr, now))

    conn.commit()
    conn.close()
    label = f"{first_name} {last_name}"
    if company:
        label += f" ({company})"
    return jsonify({"ok": True, "id": new_id, "label": label, "address": address})

@app.get("/clients/<int:client_id>")
@login_required
def client_detail(client_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    client = cur.fetchone()
    if not client:
        conn.close()
        return ("Not found", 404)
    cur.execute("""
        SELECT j.*, u.full_name agent_name
        FROM jobs j
        LEFT JOIN users u ON u.id = j.assigned_user_id
        WHERE j.client_id = ?
        ORDER BY j.created_at DESC
    """, (client_id,))
    jobs = cur.fetchall()
    cur.execute("""
        SELECT * FROM contact_phone_numbers
        WHERE entity_type = 'client' AND entity_id = ?
        ORDER BY id
    """, (client_id,))
    phones = cur.fetchall()
    conn.close()
    return render_template("client_detail.html", client=client, jobs=jobs, phones=phones)


@app.get("/clients/<int:client_id>/edit")
@login_required
@admin_required
def client_edit(client_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    client = cur.fetchone()
    if not client:
        conn.close()
        return ("Not found", 404)
    cur.execute("""
        SELECT * FROM contact_phone_numbers
        WHERE entity_type = 'client' AND entity_id = ?
        ORDER BY id
    """, (client_id,))
    phones = cur.fetchall()
    conn.close()
    return render_template("client_edit.html", client=client, phones=phones)


@app.post("/clients/<int:client_id>/edit")
@login_required
@admin_required
def client_edit_post(client_id: int):
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    notes = request.form.get("notes", "").strip()

    if not name:
        flash("Client name is required.", "danger")
        return redirect(url_for("client_edit", client_id=client_id))

    ts = now_ts()
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clients
        SET name = ?, email = ?, address = ?, notes = ?, updated_at = ?
        WHERE id = ?
    """, (name, email, address, notes, ts, client_id))

    cur.execute("""
        DELETE FROM contact_phone_numbers
        WHERE entity_type = 'client' AND entity_id = ?
    """, (client_id,))

    for label, field in [("Mobile", "phone_mobile"), ("Home", "phone_home"),
                         ("Work", "phone_work"), ("Other", "phone_other")]:
        number = request.form.get(field, "").strip()
        if number:
            cur.execute("""
                INSERT INTO contact_phone_numbers
                    (entity_type, entity_id, label, phone_number, created_at)
                VALUES ('client', ?, ?, ?, ?)
            """, (client_id, label, number, ts))

    conn.commit()
    conn.close()

    audit("client", client_id, "update", "Client details updated", {})
    flash("Client updated.", "success")
    return redirect(url_for("client_detail", client_id=client_id))


# -------- Customers --------
@app.get("/customers")
@login_required
def customers_list():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers ORDER BY last_name, first_name")
    rows = cur.fetchall()
    conn.close()
    return render_template("customers.html", customers=rows)


@app.post("/customers/delete")
@login_required
@admin_required
def customers_bulk_delete():
    customer_ids = request.form.getlist("customer_ids")
    if not customer_ids:
        flash("No customers selected.", "warning")
        return redirect(url_for("customers_list"))
    conn = db()
    cur = conn.cursor()
    deleted, skipped = 0, []
    for cid in customer_ids:
        try:
            cid = int(cid)
        except ValueError:
            continue
        cur.execute("SELECT COUNT(*) FROM jobs WHERE customer_id = ?", (cid,))
        if cur.fetchone()[0]:
            cur.execute("SELECT first_name, last_name FROM customers WHERE id = ?", (cid,))
            row = cur.fetchone()
            skipped.append(f"{row['first_name']} {row['last_name']}" if row else str(cid))
            continue
        cur.execute("DELETE FROM contact_phone_numbers WHERE entity_type='customer' AND entity_id=?", (cid,))
        cur.execute("DELETE FROM contact_emails WHERE entity_type='customer' AND entity_id=?", (cid,))
        cur.execute("DELETE FROM customers WHERE id=?", (cid,))
        deleted += 1
    conn.commit()
    conn.close()
    parts = []
    if deleted:
        parts.append(f"{deleted} customer(s) deleted.")
    if skipped:
        parts.append(f"{len(skipped)} skipped (has linked jobs): {', '.join(skipped)}.")
    flash(" ".join(parts) or "Nothing deleted.", "success" if deleted else "warning")
    return redirect(url_for("customers_list"))


@app.get("/customers/new")
@login_required
@admin_required
def customer_new():
    next_url = request.args.get("next", "")
    return render_template("customer_new.html", next_url=next_url)


@app.post("/customers/new")
@login_required
@admin_required
def customer_create():
    shared_company = request.form.get("shared_company", "").strip()
    first_names = request.form.getlist("first_name[]")
    last_names  = request.form.getlist("last_name[]")
    roles       = request.form.getlist("role[]")
    emails      = request.form.getlist("email[]")
    dobs        = request.form.getlist("dob[]")
    addresses   = request.form.getlist("address[]")
    notes_list  = request.form.getlist("notes[]")
    id_photos   = request.files.getlist("id_photo[]")

    if not first_names or not first_names[0].strip():
        flash("At least one person with a first and last name is required.", "danger")
        return redirect(url_for("customer_new"))

    ts = now_ts()
    conn = db()
    cur = conn.cursor()
    first_new_id = None
    created_count = 0

    for i in range(len(first_names)):
        fn = first_names[i].strip() if i < len(first_names) else ""
        ln = last_names[i].strip()  if i < len(last_names)  else ""
        if not fn or not ln:
            continue

        role    = roles[i].strip()    if i < len(roles)    else ""
        email   = emails[i].strip()   if i < len(emails)   else ""
        dob     = dobs[i].strip()     if i < len(dobs)     else ""
        address = addresses[i].strip() if i < len(addresses) else ""
        notes   = notes_list[i].strip() if i < len(notes_list) else ""

        id_image_filename = None
        id_image_path = None
        if i < len(id_photos):
            photo = id_photos[i]
            if photo and photo.filename:
                if not allowed_file(photo.filename):
                    flash(f"ID photo for {fn} {ln} must be PNG, JPG, JPEG, or WebP — skipped.", "warning")
                else:
                    safe_name = secure_filename(photo.filename)
                    safe_ts = ts.replace(":", "").replace("-", "").replace(" ", "")
                    stored_name = f"cust_{safe_ts}_{i}_{safe_name}"
                    upload_to_blob(photo, stored_name)
                    id_image_filename = safe_name
                    id_image_path = stored_name

        cur.execute("""
            INSERT INTO customers (first_name, last_name, company, role, email, dob, address, notes,
                                   id_image_filename, id_image_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fn, ln, shared_company or None, role or None, email or None,
              dob or None, address or None, notes or None,
              id_image_filename, id_image_path, ts, ts))
        new_id = cur.lastrowid
        if first_new_id is None:
            first_new_id = new_id
        created_count += 1

    conn.commit()
    conn.close()

    if created_count == 0:
        flash("No valid customers to create.", "warning")
        return redirect(url_for("customer_new"))

    flash(f"{created_count} customer(s) created.", "success")
    next_url = request.form.get("next_url", "")
    if next_url:
        return redirect(f"{next_url}?new_customer_id={first_new_id}")
    return redirect(url_for("customers_list"))


@app.get("/customers/<int:customer_id>")
@login_required
def customer_detail(customer_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        conn.close()
        return ("Not found", 404)
    cur.execute("""
        SELECT j.*, c.name client_name
        FROM jobs j
        LEFT JOIN clients c ON c.id = j.client_id
        WHERE j.customer_id = ?
        ORDER BY j.created_at DESC
    """, (customer_id,))
    jobs = cur.fetchall()
    cur.execute("""
        SELECT * FROM contact_phone_numbers
        WHERE entity_type = 'customer' AND entity_id = ?
        ORDER BY id
    """, (customer_id,))
    phones = cur.fetchall()

    cur.execute("""
        SELECT * FROM contact_emails
        WHERE entity_type = 'customer' AND entity_id = ?
        ORDER BY id
    """, (customer_id,))
    emails = cur.fetchall()

    conn.close()
    return render_template("customer_detail.html", customer=customer, jobs=jobs, phones=phones, emails=emails)


@app.get("/customers/<int:customer_id>/edit")
@login_required
@admin_required
def customer_edit(customer_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        conn.close()
        return ("Not found", 404)
    cur.execute("""
        SELECT * FROM contact_phone_numbers
        WHERE entity_type = 'customer' AND entity_id = ?
        ORDER BY id
    """, (customer_id,))
    phones = cur.fetchall()
    conn.close()
    return render_template("customer_edit.html", customer=customer, phones=phones)


@app.post("/customers/<int:customer_id>/edit")
@login_required
@admin_required
def customer_edit_post(customer_id: int):
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    company = request.form.get("company", "").strip()
    role = request.form.get("role", "").strip()
    email = request.form.get("email", "").strip()
    dob = request.form.get("dob", "").strip()
    address = request.form.get("address", "").strip()
    notes = request.form.get("notes", "").strip()
    id_image = request.files.get("id_image")

    if not first_name or not last_name:
        flash("First and last name are required.", "danger")
        return redirect(url_for("customer_edit", customer_id=customer_id))

    ts = now_ts()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id_image_filename, id_image_path FROM customers WHERE id = ?", (customer_id,))
    existing = cur.fetchone()

    id_image_filename = existing["id_image_filename"] if existing else None
    id_image_path = existing["id_image_path"] if existing else None

    if id_image and id_image.filename:
        if not allowed_file(id_image.filename):
            conn.close()
            flash("Unsupported file type. Use PNG/JPG/PDF.", "danger")
            return redirect(url_for("customer_edit", customer_id=customer_id))
        filename = secure_filename(id_image.filename)
        safe_ts = ts.replace(":", "").replace("-", "").replace(" ", "")
        unique_name = f"customer_{customer_id}_id_{safe_ts}_{filename}"
        upload_to_blob(id_image, unique_name)
        id_image_filename = filename
        id_image_path = unique_name

    cur.execute("""
        UPDATE customers
        SET first_name = ?, last_name = ?, company = ?, role = ?, email = ?, dob = ?, address = ?, notes = ?,
            id_image_filename = ?, id_image_path = ?, updated_at = ?
        WHERE id = ?
    """, (first_name, last_name, company or None, role or None, email or None, dob or None, address or None, notes or None,
          id_image_filename, id_image_path, ts, customer_id))

    cur.execute("""
        DELETE FROM contact_phone_numbers
        WHERE entity_type = 'customer' AND entity_id = ?
    """, (customer_id,))

    for label, field in [("Mobile", "phone_mobile"), ("Home", "phone_home"),
                         ("Work", "phone_work"), ("Other", "phone_other")]:
        number = request.form.get(field, "").strip()
        if number:
            cur.execute("""
                INSERT INTO contact_phone_numbers
                    (entity_type, entity_id, label, phone_number, created_at)
                VALUES ('customer', ?, ?, ?, ?)
            """, (customer_id, label, number, ts))

    conn.commit()
    conn.close()

    audit("customer", customer_id, "update", "Customer details updated",
          {"id_image_updated": bool(id_image and id_image.filename)})

    flash("Customer updated.", "success")
    return redirect(url_for("customer_detail", customer_id=customer_id))


# -------- Customer Delete --------
@app.post("/customers/<int:customer_id>/delete")
@login_required
@admin_required
def customer_delete(customer_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jobs WHERE customer_id = ?", (customer_id,))
    job_count = cur.fetchone()[0]
    if job_count:
        conn.close()
        flash(f"Cannot delete — this customer has {job_count} linked job(s).", "danger")
        return redirect(url_for("customer_detail", customer_id=customer_id))
    cur.execute("DELETE FROM contact_phone_numbers WHERE entity_type = 'customer' AND entity_id = ?", (customer_id,))
    cur.execute("DELETE FROM contact_emails WHERE entity_type = 'customer' AND entity_id = ?", (customer_id,))
    cur.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    flash("Customer deleted.", "success")
    return redirect(url_for("customers_list"))


# -------- Job Items --------
@app.post("/jobs/<int:job_id>/items/new")
@login_required
@admin_required
def job_item_create(job_id: int):
    item_type        = request.form.get("item_type", "vehicle").strip()
    description      = request.form.get("description", "").strip()
    reg              = request.form.get("reg", "").strip()
    vin              = request.form.get("vin", "").strip()
    make             = request.form.get("make", "").strip()
    model            = request.form.get("model", "").strip()
    year             = request.form.get("year", "").strip()
    property_address = request.form.get("property_address", "").strip()
    lot_details      = request.form.get("lot_details", "").strip()
    serial_number    = request.form.get("serial_number", "").strip()
    identifier       = request.form.get("identifier", "").strip()
    notes            = request.form.get("notes", "").strip()
    item_lender      = request.form.get("item_lender_name", "").strip()
    item_account     = request.form.get("item_account_number", "").strip()
    item_regulation  = request.form.get("item_regulation_type", "").strip()

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO job_items (
            job_id, item_type, description,
            reg, vin, make, model, year,
            property_address, lot_details,
            serial_number, identifier,
            notes, lender_name, account_number, regulation_type,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id, item_type, description or None,
        reg or None, vin or None, make or None, model or None, year or None,
        property_address or None, lot_details or None,
        serial_number or None, identifier or None,
        notes or None, item_lender or None, item_account or None, item_regulation or None,
        now_ts()
    ))
    conn.commit()
    conn.close()

    flash("Item added.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.post("/jobs/<int:job_id>/items/<int:item_id>/delete")
@login_required
@admin_required
def job_item_delete(job_id: int, item_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM job_items WHERE id = ? AND job_id = ?", (item_id, job_id))
    conn.commit()
    conn.close()
    flash("Item removed.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


# -------- Field Notes --------
@app.post("/jobs/<int:job_id>/notes/new")
@login_required
def add_job_note(job_id: int):
    note_text = request.form.get("note_text", "").strip()
    files = request.files.getlist("attachments")

    if not note_text and not any(f.filename for f in files):
        flash("A note or attachment is required.", "danger")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="tab-notes"))

    ts = now_ts()
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO job_field_notes (job_id, created_by_user_id, note_text, created_at)
        VALUES (?, ?, ?, ?)
    """, (job_id, session.get("user_id"), note_text, ts))

    note_id = cur.lastrowid

    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename    = secure_filename(file.filename)
            unique_name = f"{job_id}_{note_id}_{filename}"
            upload_to_blob(file, unique_name)
            cur.execute("""
                INSERT INTO job_note_files (job_field_note_id, filename, filepath, uploaded_at)
                VALUES (?, ?, ?, ?)
            """, (note_id, unique_name, unique_name, ts))

    conn.commit()
    conn.close()

    audit("job_note", note_id, "create", "Field note added", {"job_id": job_id})
    flash("Field note saved.", "success")
    return redirect(url_for("job_detail", job_id=job_id, _anchor="tab-notes"))


@app.post("/jobs/<int:job_id>/notes/<int:note_id>/delete")
@login_required
def delete_job_note(job_id: int, note_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM job_field_notes WHERE id = ? AND job_id = ?", (note_id, job_id))
    note = cur.fetchone()
    if not note:
        conn.close()
        flash("Note not found.", "danger")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="tab-notes"))

    caller_id   = session.get("user_id")
    caller_role = session.get("role", "")
    if caller_role != "admin" and note["created_by_user_id"] != caller_id:
        conn.close()
        flash("You can only delete your own notes.", "danger")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="tab-notes"))

    cur.execute("SELECT filename, filepath FROM job_note_files WHERE job_field_note_id = ?", (note_id,))
    files = cur.fetchall()
    for f in files:
        delete_blob_safely(f["filename"])
        try: os.remove(f["filepath"])
        except OSError: pass
    cur.execute("DELETE FROM job_note_files WHERE job_field_note_id = ?", (note_id,))
    cur.execute("DELETE FROM job_field_notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()

    audit("job_note", note_id, "delete", "Field note deleted", {"job_id": job_id})
    flash("Field note deleted.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.get("/uploads/<path:filename>")
@login_required
def serve_upload(filename):
    if _uploads_container:
        try:
            blob_client = _uploads_container.get_blob_client(filename)
            download    = blob_client.download_blob()
            mime        = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            return Response(download.readall(), mimetype=mime)
        except Exception:
            pass
    local_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(local_path):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)
    abort(404)


@app.post("/jobs/<int:job_id>/documents/upload")
@login_required
@admin_required
def job_document_upload(job_id: int):
    doc_type = (request.form.get("doc_type") or "Other").strip()
    title = (request.form.get("title") or "").strip()
    notes = (request.form.get("notes") or "").strip()
    files = request.files.getlist("file")

    valid_files = [f for f in files if f and f.filename]
    if not valid_files:
        flash("Select at least one file to upload.", "danger")
        return redirect(url_for("job_detail", job_id=job_id))

    conn = db()
    cur = conn.cursor()
    uploaded = 0
    skipped = []
    for file in valid_files:
        if not allowed_file(file.filename):
            skipped.append(file.filename)
            continue
        original_filename = secure_filename(file.filename)
        ts_safe = now_ts().replace(":", "").replace("-", "").replace(" ", "")
        stored_filename = f"job_{job_id}_{ts_safe}_{original_filename}"
        mime_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
        file_size = upload_to_blob(file, stored_filename)
        cur.execute("""
            INSERT INTO job_documents
                (job_id, doc_type, title, original_filename, stored_filename,
                 mime_type, file_size, uploaded_by_user_id, uploaded_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, doc_type, title or None, original_filename, stored_filename,
              mime_type, file_size, session.get("user_id"), now_ts(), notes or None))
        doc_id = cur.lastrowid
        audit("job_document", doc_id, "create", "Job document uploaded",
              {"job_id": job_id, "doc_type": doc_type, "filename": original_filename})
        uploaded += 1
    conn.commit()
    conn.close()

    if uploaded:
        msg = f"{uploaded} document{'s' if uploaded != 1 else ''} uploaded."
        if skipped:
            msg += f" {len(skipped)} skipped (unsupported type)."
        flash(msg, "success")
    else:
        flash("No supported files were uploaded.", "danger")
    return redirect(url_for("job_detail", job_id=job_id))


# -------- Users (admin only) --------
@app.get("/users")
@admin_required
def users_list():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY full_name")
    rows = cur.fetchall()
    conn.close()
    return render_template("users.html", users=rows)


@app.get("/users/new")
@admin_required
def user_new():
    next_url = request.args.get("next", "").strip()
    return render_template("user_new.html", next_url=next_url)


@app.post("/users/new")
@admin_required
def user_create():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "agent").strip()
    next_url = request.form.get("next_url", "").strip()

    if not full_name or not email or not password:
        flash("Name, email and password are required.", "danger")
        dest = url_for("user_new")
        if next_url:
            dest += "?next=" + next_url
        return redirect(dest)

    hashed = generate_password_hash(password)
    conn = db()
    cur = conn.cursor()
    user_id = None
    try:
        cur.execute("""
            INSERT INTO users (full_name, email, password, role, active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (full_name, email, hashed, role, now_ts()))
        user_id = cur.lastrowid
        conn.commit()
        audit("user", user_id, "create", f"User created: {full_name} ({role})", {"email": email, "role": role})
        flash("User created.", "success")
    except sqlite3.IntegrityError:
        flash("Email already in use.", "danger")
    finally:
        conn.close()

    if next_url and user_id:
        return redirect(f"{next_url}?new_user_id={user_id}")
    return redirect(url_for("users_list"))



@app.get("/users/new-popup")
@admin_required
def user_new_popup():
    return render_template("partials/user_popup.html")


@app.post("/users/new-popup")
@admin_required
def user_create_popup():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "agent").strip()
    if not full_name or not email or not password:
        return jsonify({"ok": False, "error": "Name, email and password are all required."})
    hashed = generate_password_hash(password)
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (full_name, email, password, role, active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (full_name, email, hashed, role, now_ts()))
        new_id = cur.lastrowid
        conn.commit()
        audit("user", new_id, "create", f"User created via popup: {full_name} ({role})", {"email": email, "role": role})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"ok": False, "error": "That email address is already in use."})
    conn.close()
    return jsonify({"ok": True, "id": new_id, "label": full_name})

@app.get("/admin/users/new")
@admin_required
def admin_user_new():
    return redirect(url_for("user_new"))


@app.post("/admin/users/new")
@admin_required
def admin_user_create():
    return redirect(url_for("user_create"))


# -------- CSV Import --------
@app.get("/import/jobs")
@admin_required
def import_jobs_form():
    return render_template("import_jobs.html")


@app.post("/import/jobs")
@admin_required
def import_jobs():
    file = request.files.get("file")
    if not file:
        flash("No file uploaded.", "danger")
        return redirect(url_for("import_jobs_form"))

    conn = db()
    cur = conn.cursor()
    reader = csv.DictReader(file.stream.read().decode("utf-8").splitlines())

    imported = 0
    skipped = 0
    now = datetime.now().isoformat(timespec="seconds")

    for row in reader:
        internal_job_number = (row.get("InternalJobNumber") or "").strip()
        if not internal_job_number:
            skipped += 1
            continue

        client_reference = (row.get("ClientReference") or "").strip()
        display_ref = internal_job_number
        if client_reference:
            display_ref = f"{internal_job_number} ({client_reference})"

        cur.execute("""
            INSERT OR IGNORE INTO jobs (
                internal_job_number, client_reference, display_ref,
                job_type, visit_type, status, priority,
                job_address, description,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            internal_job_number,
            client_reference or None,
            display_ref,
            (row.get("JobType") or "Field Call").strip(),
            (row.get("VisitType") or "New Visit").strip(),
            (row.get("Status") or "New").strip(),
            (row.get("Priority") or "Normal").strip(),
            (row.get("JobAddress") or "").strip() or None,
            (row.get("Description") or "").strip() or None,
            now, now
        ))
        if cur.rowcount:
            imported += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()

    flash(f"Import complete: {imported} imported, {skipped} skipped.", "success")
    return redirect(url_for("import_jobs_form"))


# -------- Admin dashboard --------
@app.get("/admin")
@admin_required
def admin_dashboard():
    today = datetime.now().date().isoformat()
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) c FROM cue_items WHERE due_date = ? AND status IN ('Pending','In Progress')", (today,))
    cues_today = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) c FROM cue_items WHERE due_date < ? AND status IN ('Pending','In Progress')", (today,))
    cues_overdue = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) c FROM cue_items WHERE assigned_user_id IS NULL AND status IN ('Pending','In Progress')")
    cues_unassigned = cur.fetchone()["c"]

    cur.execute("SELECT status, COUNT(*) c FROM jobs GROUP BY status ORDER BY c DESC")
    jobs_by_status = cur.fetchall()

    cur.execute("""
        SELECT a.*, u.full_name actor_name
        FROM audit_log a
        LEFT JOIN users u ON u.id = a.actor_user_id
        ORDER BY a.id DESC
        LIMIT 20
    """)
    recent = cur.fetchall()

    conn.close()
    return render_template("admin.html",
                           today=today,
                           cues_today=cues_today,
                           cues_overdue=cues_overdue,
                           cues_unassigned=cues_unassigned,
                           jobs_by_status=jobs_by_status,
                           recent=recent)


# -------- Admin Settings --------

@app.get("/admin/settings/popup")
@admin_required
def admin_settings_popup():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM system_settings WHERE id = 1")
    settings = cur.fetchone()
    conn.close()
    return render_template("partials/settings_popup.html", settings=settings)


@app.post("/admin/settings/popup")
@admin_required
def admin_settings_popup_update():
    prefix   = request.form.get("job_prefix", "").strip()
    sequence = request.form.get("job_sequence", "0").strip()
    auto_enabled = 1 if request.form.get("auto_prefix_enabled") == "on" else 0

    if not prefix:
        return jsonify({"ok": False, "error": "Job prefix is required."})

    try:
        seq_int = int(sequence)
    except ValueError:
        return jsonify({"ok": False, "error": "Sequence must be a number."})

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE system_settings
        SET job_prefix = ?, job_sequence = ?, auto_prefix_enabled = ?, updated_at = ?
        WHERE id = 1
    """, (prefix, seq_int, auto_enabled, now_ts()))
    conn.commit()
    conn.close()

    audit("system", 1, "update", "Job numbering settings updated via popup",
          {"prefix": prefix, "sequence": sequence, "auto_enabled": auto_enabled})

    next_number = f"{prefix}{str(seq_int + 1).zfill(3)}"
    return jsonify({"ok": True, "next_number": next_number})

@app.get("/admin/settings")
@admin_required
def admin_settings():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM system_settings WHERE id = 1")
    settings = cur.fetchone()
    cur.execute("SELECT * FROM booking_types ORDER BY name")
    booking_types = cur.fetchall()
    conn.close()
    return render_template("settings.html", settings=settings, booking_types=booking_types)


@app.post("/admin/settings")
@admin_required
def admin_settings_update():
    prefix = request.form.get("job_prefix", "").strip()
    sequence = request.form.get("job_sequence", "0").strip()
    auto_enabled = 1 if request.form.get("auto_prefix_enabled") == "on" else 0

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE system_settings
        SET job_prefix = ?, job_sequence = ?, auto_prefix_enabled = ?, updated_at = ?
        WHERE id = 1
    """, (prefix, int(sequence), auto_enabled, now_ts()))
    conn.commit()
    conn.close()

    audit("system", 1, "update",
          "Job numbering settings updated",
          {"prefix": prefix, "sequence": sequence, "auto_enabled": auto_enabled})

    flash("Settings saved.", "success")
    return redirect(url_for("admin_settings"))


# -------- Cues --------
@app.get("/queue")
@admin_required
def job_queue():
    date = request.args.get("date", datetime.now().date().isoformat())
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT ci.*, j.internal_job_number, j.client_reference, j.status job_status,
               j.job_address,
               (cu.first_name || ' ' || cu.last_name) customer_name,
               (SELECT ji.reg FROM job_items ji WHERE ji.job_id = j.id AND ji.item_type = 'vehicle' LIMIT 1) asset_reg,
               u.full_name assigned_name
        FROM cue_items ci
        JOIN jobs j ON j.id = ci.job_id
        LEFT JOIN customers cu ON cu.id = j.customer_id
        LEFT JOIN users u ON u.id = ci.assigned_user_id
        WHERE ci.due_date = ?
        ORDER BY ci.priority DESC, ci.id DESC
    """, (date,))
    cues = cur.fetchall()

    cur.execute("SELECT id, full_name FROM users WHERE role = 'agent' AND active = 1 ORDER BY full_name")
    agents = cur.fetchall()

    conn.close()
    return render_template("queue.html", cues=cues, agents=agents, date=date)


@app.post("/queue/new")
@admin_required
def cue_create():
    job_id = request.form.get("job_id", "").strip()
    visit_type = request.form.get("visit_type", "New Visit")
    due_date = request.form.get("due_date", "").strip()
    assigned_user_id = request.form.get("assigned_user_id") or None
    priority = request.form.get("priority", "Normal")
    instructions = request.form.get("instructions", "").strip()

    if not job_id or not due_date:
        flash("Job ID and due date are required.", "danger")
        return redirect(url_for("job_queue", date=due_date))

    ts = now_ts()
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cue_items (job_id, visit_type, due_date, priority, status, assigned_user_id, instructions, created_by_user_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'Pending', ?, ?, ?, ?, ?)
    """, (job_id, visit_type, due_date, priority, assigned_user_id, instructions or None, session.get("user_id"), ts, ts))
    cue_id = cur.lastrowid
    conn.commit()
    conn.close()

    audit("cue", cue_id, "create",
          f"Cue created for job {job_id} due {due_date} ({visit_type}).",
          {"job_id": job_id, "due_date": due_date, "visit_type": visit_type, "assigned_user_id": assigned_user_id})

    flash("Item added to queue.", "success")
    return redirect(url_for("job_queue", date=due_date))


@app.post("/cue/<int:cue_id>/complete")
@login_required
def cue_complete(cue_id: int):
    ts = now_ts()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cue_items WHERE id = ?", (cue_id,))
    cue = cur.fetchone()
    if not cue:
        conn.close()
        return ("Not found", 404)

    cur.execute("UPDATE cue_items SET status = 'Completed', completed_at = ?, updated_at = ? WHERE id = ?",
                (ts, ts, cue_id))
    conn.commit()
    conn.close()

    audit("cue", cue_id, "status_change", f"Cue {cue_id} marked Completed.")

    referrer = request.referrer or url_for("my_today")
    return redirect(referrer)


# -------- Assignment board --------
@app.get("/assign")
@admin_required
def assign_board():
    date = request.args.get("date", datetime.now().date().isoformat())
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT id, full_name FROM users WHERE role='agent' AND active=1 ORDER BY full_name")
    agents = cur.fetchall()

    cur.execute("""
        SELECT ci.*, j.internal_job_number, j.client_reference,
               (cu.first_name || ' ' || cu.last_name) customer_name,
               (SELECT ji.reg FROM job_items ji WHERE ji.job_id = j.id AND ji.item_type = 'vehicle' LIMIT 1) asset_reg
        FROM cue_items ci
        JOIN jobs j ON j.id = ci.job_id
        LEFT JOIN customers cu ON cu.id = j.customer_id
        WHERE ci.due_date = ? AND ci.status IN ('Pending','In Progress')
        ORDER BY ci.priority DESC, ci.id DESC
    """, (date,))
    cues = cur.fetchall()

    conn.close()
    return render_template("assign.html", date=date, agents=agents, cues=cues)


@app.post("/cue/<int:cue_id>/assign")
@admin_required
def cue_assign(cue_id: int):
    assigned_user_id = request.form.get("assigned_user_id") or None
    ts = now_ts()

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT assigned_user_id, job_id FROM cue_items WHERE id = ?", (cue_id,))
    before = cur.fetchone()
    if not before:
        conn.close()
        return ("Not found", 404)

    cur.execute("UPDATE cue_items SET assigned_user_id = ?, updated_at = ? WHERE id = ?",
                (assigned_user_id, ts, cue_id))
    conn.commit()
    conn.close()

    audit("cue", cue_id, "assign",
          f"Cue {cue_id} assigned to user {assigned_user_id or 'Unassigned'}.",
          {"from": before["assigned_user_id"], "to": assigned_user_id, "job_id": before["job_id"]})

    return ("OK", 200)


# -------- Monthly report --------
@app.get("/reports/monthly")
@admin_required
def report_monthly():
    prefix = request.args.get("prefix") or datetime.now().strftime("%y%m")

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) c FROM jobs
        WHERE strftime('%y%m', created_at) = ?
    """, (prefix,))
    total_jobs = cur.fetchone()["c"]

    cur.execute("""
        SELECT status, COUNT(*) c FROM jobs
        WHERE strftime('%y%m', created_at) = ?
        GROUP BY status ORDER BY c DESC
    """, (prefix,))
    by_status = cur.fetchall()

    cur.execute("""
        SELECT u.full_name, COUNT(*) c
        FROM cue_items ci
        JOIN users u ON u.id = ci.assigned_user_id
        JOIN jobs j ON j.id = ci.job_id
        WHERE strftime('%y%m', j.created_at) = ? AND ci.status = 'Completed'
        GROUP BY u.full_name
        ORDER BY c DESC
    """, (prefix,))
    completed_by_agent = cur.fetchall()

    conn.close()
    return render_template("report_monthly.html",
                           prefix=prefix,
                           total_jobs=total_jobs,
                           by_status=by_status,
                           completed_by_agent=completed_by_agent)


# -------- Agent: My Today --------
@app.get("/my/today")
@login_required
def my_today():
    today = datetime.now().date().isoformat()
    user_id = session.get("user_id")

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT ci.*, j.internal_job_number, j.client_reference, j.job_address,
               (cu.first_name || ' ' || cu.last_name) customer_name,
               (SELECT ji.reg FROM job_items ji WHERE ji.job_id = j.id AND ji.item_type = 'vehicle' LIMIT 1) asset_reg
        FROM cue_items ci
        JOIN jobs j ON j.id = ci.job_id
        LEFT JOIN customers cu ON cu.id = j.customer_id
        WHERE ci.due_date = ? AND ci.assigned_user_id = ?
          AND ci.status IN ('Pending','In Progress')
        ORDER BY ci.priority DESC, ci.id
    """, (today, user_id))
    cues = cur.fetchall()
    conn.close()

    return render_template("my_today.html", cues=cues, today=today)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
