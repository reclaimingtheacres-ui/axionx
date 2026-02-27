from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sqlite3
import csv
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "axion-dev-secret"

DB_PATH = "axion.db"


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
        full_name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        dob TEXT,
        address TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reg TEXT,
        vin TEXT,
        make TEXT,
        model TEXT,
        year INTEGER,
        notes TEXT,
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
        asset_id INTEGER,
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
        FOREIGN KEY(asset_id) REFERENCES assets(id),
        FOREIGN KEY(assigned_user_id) REFERENCES users(id)
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

    cur.execute("SELECT COUNT(*) AS c FROM users")
    if cur.fetchone()["c"] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        cur.execute("""
            INSERT INTO users (full_name, email, password, role, active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, ("Admin", "admin@axion.local", "admin", "admin", now))

    conn.commit()
    conn.close()


@app.before_request
def _ensure_db():
    init_db()


# -------- Helpers --------
def now_ts():
    return datetime.now().isoformat(timespec="seconds")


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
@app.get("/login")
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
    return render_template("login.html")


@app.post("/login")
def login_post():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ? AND active = 1", (email,))
    user = cur.fetchone()
    conn.close()

    if not user or user["password"] != password:
        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    session["user_id"] = user["id"]
    session["user_name"] = user["full_name"]
    session["role"] = user["role"]
    return redirect(url_for("index"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------- Home --------
@app.get("/")
@login_required
def index():
    conn = db()
    cur = conn.cursor()
    role = session.get("role")
    user_id = session.get("user_id")

    if role == "admin":
        cur.execute("SELECT COUNT(*) AS c FROM jobs")
    else:
        cur.execute("SELECT COUNT(*) AS c FROM jobs WHERE assigned_user_id = ?", (user_id,))
    jobs_count = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM clients")
    clients_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM customers")
    customers_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM assets")
    assets_count = cur.fetchone()["c"]
    conn.close()
    return render_template("index.html",
                           jobs_count=jobs_count,
                           clients_count=clients_count,
                           customers_count=customers_count,
                           assets_count=assets_count)


# -------- Jobs --------
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
           cu.full_name AS customer_name,
           a.reg AS asset_reg,
           u.full_name AS assigned_name
    FROM jobs j
    LEFT JOIN clients c ON c.id = j.client_id
    LEFT JOIN customers cu ON cu.id = j.customer_id
    LEFT JOIN assets a ON a.id = j.asset_id
    LEFT JOIN users u ON u.id = j.assigned_user_id
    WHERE 1=1
    """
    params = []

    if role == "agent":
        sql += " AND j.assigned_user_id = ?"
        params.append(user_id)

    if status:
        sql += " AND j.status = ?"
        params.append(status)

    if q:
        sql += " AND (j.internal_job_number LIKE ? OR j.client_reference LIKE ? OR j.display_ref LIKE ? OR j.description LIKE ? OR cu.full_name LIKE ? OR a.reg LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like, like, like, like])

    sql += " ORDER BY j.updated_at DESC"

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
def job_new():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM clients ORDER BY name")
    clients = cur.fetchall()
    cur.execute("SELECT id, full_name FROM customers ORDER BY full_name")
    customers = cur.fetchall()
    cur.execute("SELECT id, reg, make, model FROM assets ORDER BY reg")
    assets = cur.fetchall()
    cur.execute("SELECT id, full_name FROM users WHERE active = 1 ORDER BY full_name")
    users = cur.fetchall()
    conn.close()

    visit_types = ["New Visit", "Re-attend", "First Update", "Urgent Update", "Phone Follow-up", "Locate Only"]
    job_types = ["Field Call", "Repo/Collect", "Repo Only", "Locate", "Phone Work"]
    statuses = ["New", "Active", "Active - Phone work only", "Suspended", "Awaiting info from client", "Completed", "Invoiced"]
    priorities = ["Low", "Normal", "High", "Urgent"]

    return render_template("job_new.html", clients=clients, customers=customers, assets=assets,
                           users=users, visit_types=visit_types, job_types=job_types,
                           statuses=statuses, priorities=priorities)


@app.post("/jobs/new")
@login_required
def job_create():
    internal_job_number = request.form.get("internal_job_number", "").strip()
    client_reference = request.form.get("client_reference", "").strip()
    client_id = request.form.get("client_id") or None
    customer_id = request.form.get("customer_id") or None
    asset_id = request.form.get("asset_id") or None
    assigned_user_id = request.form.get("assigned_user_id") or None
    job_type = request.form.get("job_type", "Field Call").strip()
    visit_type = request.form.get("visit_type", "New Visit").strip()
    status = request.form.get("status", "New").strip()
    priority = request.form.get("priority", "Normal").strip()
    job_address = request.form.get("job_address", "").strip()
    description = request.form.get("description", "").strip()

    if not internal_job_number:
        flash("Internal job number is required.", "danger")
        return redirect(url_for("job_new"))

    display_ref = internal_job_number
    if client_reference:
        display_ref = f"{internal_job_number} ({client_reference})"

    now = datetime.now().isoformat(timespec="seconds")

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO jobs (
            internal_job_number, client_reference, display_ref,
            client_id, customer_id, asset_id, assigned_user_id,
            job_type, visit_type, status, priority,
            job_address, description, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        internal_job_number, client_reference or None, display_ref,
        client_id, customer_id, asset_id, assigned_user_id,
        job_type, visit_type, status, priority,
        job_address, description, now, now
    ))
    job_id = cur.lastrowid

    cur.execute("""
        INSERT INTO interactions (job_id, event_type, narrative, occurred_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, "System", f"Job created: {display_ref}. Status '{status}'. Visit type '{visit_type}'.", now, now))

    conn.commit()
    conn.close()

    flash("Job created.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.get("/jobs/<int:job_id>")
@login_required
def job_detail(job_id: int):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT j.*,
           c.name AS client_name, c.phone AS client_phone, c.email AS client_email, c.address AS client_address,
           cu.full_name AS customer_name, cu.phone AS customer_phone, cu.email AS customer_email, cu.dob AS customer_dob, cu.address AS customer_address,
           a.reg AS asset_reg, a.vin AS asset_vin, a.make AS asset_make, a.model AS asset_model, a.year AS asset_year,
           u.full_name AS assigned_name
    FROM jobs j
    LEFT JOIN clients c ON c.id = j.client_id
    LEFT JOIN customers cu ON cu.id = j.customer_id
    LEFT JOIN assets a ON a.id = j.asset_id
    LEFT JOIN users u ON u.id = j.assigned_user_id
    WHERE j.id = ?
    """, (job_id,))
    job = cur.fetchone()
    if not job:
        conn.close()
        return ("Not found", 404)

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

    cur.execute("SELECT id, full_name FROM users WHERE active = 1 ORDER BY full_name")
    users = cur.fetchall()

    conn.close()

    statuses = ["New", "Active", "Active - Phone work only", "Suspended", "Awaiting info from client", "Completed", "Invoiced"]
    visit_types = ["New Visit", "Re-attend", "First Update", "Urgent Update", "Phone Follow-up", "Locate Only"]

    return render_template("job_detail.html", job=job, interactions=interactions,
                           statuses=statuses, visit_types=visit_types, users=users)


@app.post("/jobs/<int:job_id>/update")
@login_required
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

    conn.commit()
    conn.close()
    flash("Job updated.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.post("/jobs/<int:job_id>/interactions/new")
@login_required
def interaction_add(job_id: int):
    event_type = request.form.get("event_type", "Note").strip()
    narrative = request.form.get("narrative", "").strip()
    occurred_at = request.form.get("occurred_at", "").strip()

    if not narrative:
        flash("Narrative text is required.", "danger")
        return redirect(url_for("job_detail", job_id=job_id))

    if not occurred_at:
        occurred_at = datetime.now().isoformat(timespec="seconds")

    now = datetime.now().isoformat(timespec="seconds")

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO interactions (job_id, event_type, narrative, occurred_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, event_type, narrative, occurred_at, now))
    cur.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (now, job_id))
    conn.commit()
    conn.close()

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


@app.get("/clients/new")
@login_required
def client_new():
    return render_template("client_new.html")


@app.post("/clients/new")
@login_required
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
    conn.commit()
    conn.close()
    flash("Client created.", "success")
    return redirect(url_for("clients_list"))


# -------- Customers --------
@app.get("/customers")
@login_required
def customers_list():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers ORDER BY full_name")
    rows = cur.fetchall()
    conn.close()
    return render_template("customers.html", customers=rows)


@app.get("/customers/new")
@login_required
def customer_new():
    return render_template("customer_new.html")


@app.post("/customers/new")
@login_required
def customer_create():
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    dob = request.form.get("dob", "").strip()
    address = request.form.get("address", "").strip()
    notes = request.form.get("notes", "").strip()

    if not full_name:
        flash("Customer name is required.", "danger")
        return redirect(url_for("customer_new"))

    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO customers (full_name, phone, email, dob, address, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (full_name, phone, email, dob, address, notes, now))
    conn.commit()
    conn.close()
    flash("Customer created.", "success")
    return redirect(url_for("customers_list"))


# -------- Assets --------
@app.get("/assets")
@login_required
def assets_list():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM assets ORDER BY reg")
    rows = cur.fetchall()
    conn.close()
    return render_template("assets.html", assets=rows)


@app.get("/assets/new")
@login_required
def asset_new():
    return render_template("asset_new.html")


@app.post("/assets/new")
@login_required
def asset_create():
    reg = request.form.get("reg", "").strip()
    vin = request.form.get("vin", "").strip()
    make = request.form.get("make", "").strip()
    model = request.form.get("model", "").strip()
    year = request.form.get("year", "").strip()
    notes = request.form.get("notes", "").strip()

    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO assets (reg, vin, make, model, year, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (reg, vin, make, model, int(year) if year.isdigit() else None, notes, now))
    conn.commit()
    conn.close()
    flash("Asset created.", "success")
    return redirect(url_for("assets_list"))


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
    return render_template("user_new.html")


@app.post("/users/new")
@admin_required
def user_create():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "agent").strip()

    if not full_name or not email or not password:
        flash("Name, email and password are required.", "danger")
        return redirect(url_for("user_new"))

    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (full_name, email, password, role, active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (full_name, email, password, role, now))
        conn.commit()
        flash("User created.", "success")
    except sqlite3.IntegrityError:
        flash("Email already in use.", "danger")
    finally:
        conn.close()

    return redirect(url_for("users_list"))


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


# -------- Cues --------
@app.get("/cues")
@admin_required
def cues_list():
    date = request.args.get("date", datetime.now().date().isoformat())
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT ci.*, j.internal_job_number, j.client_reference, j.status job_status,
               j.job_address,
               cu.full_name customer_name, a.reg asset_reg,
               u.full_name assigned_name
        FROM cue_items ci
        JOIN jobs j ON j.id = ci.job_id
        LEFT JOIN customers cu ON cu.id = j.customer_id
        LEFT JOIN assets a ON a.id = j.asset_id
        LEFT JOIN users u ON u.id = ci.assigned_user_id
        WHERE ci.due_date = ?
        ORDER BY ci.priority DESC, ci.id DESC
    """, (date,))
    cues = cur.fetchall()

    cur.execute("SELECT id, full_name FROM users WHERE role = 'agent' AND active = 1 ORDER BY full_name")
    agents = cur.fetchall()

    conn.close()
    return render_template("cues.html", cues=cues, agents=agents, date=date)


@app.post("/cues/new")
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
        return redirect(url_for("cues_list", date=due_date))

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

    flash("Cue added.", "success")
    return redirect(url_for("cues_list", date=due_date))


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
               cu.full_name customer_name, a.reg asset_reg
        FROM cue_items ci
        JOIN jobs j ON j.id = ci.job_id
        LEFT JOIN customers cu ON cu.id = j.customer_id
        LEFT JOIN assets a ON a.id = j.asset_id
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
               cu.full_name customer_name, a.reg asset_reg
        FROM cue_items ci
        JOIN jobs j ON j.id = ci.job_id
        LEFT JOIN customers cu ON cu.id = j.customer_id
        LEFT JOIN assets a ON a.id = j.asset_id
        WHERE ci.due_date = ? AND ci.assigned_user_id = ?
          AND ci.status IN ('Pending','In Progress')
        ORDER BY ci.priority DESC, ci.id
    """, (today, user_id))
    cues = cur.fetchall()
    conn.close()

    return render_template("my_today.html", cues=cues, today=today)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
