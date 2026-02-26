from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
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
        FOREIGN KEY(asset_id) REFERENCES assets(id)
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

    conn.commit()
    conn.close()


@app.before_request
def _ensure_db():
    init_db()


# -------- Home --------
@app.get("/")
def index():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM jobs")
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
def jobs_list():
    status = request.args.get("status", "").strip()
    q = request.args.get("q", "").strip()

    conn = db()
    cur = conn.cursor()

    sql = """
    SELECT j.*,
           c.name AS client_name,
           cu.full_name AS customer_name,
           a.reg AS asset_reg
    FROM jobs j
    LEFT JOIN clients c ON c.id = j.client_id
    LEFT JOIN customers cu ON cu.id = j.customer_id
    LEFT JOIN assets a ON a.id = j.asset_id
    WHERE 1=1
    """
    params = []

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
def job_new():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM clients ORDER BY name")
    clients = cur.fetchall()
    cur.execute("SELECT id, full_name FROM customers ORDER BY full_name")
    customers = cur.fetchall()
    cur.execute("SELECT id, reg, make, model FROM assets ORDER BY reg")
    assets = cur.fetchall()
    conn.close()

    visit_types = ["New Visit", "Re-attend", "First Update", "Urgent Update", "Phone Follow-up", "Locate Only"]
    job_types = ["Field Call", "Repo/Collect", "Repo Only", "Locate", "Phone Work"]
    statuses = ["New", "Active", "Active - Phone work only", "Suspended", "Awaiting info from client", "Completed", "Invoiced"]
    priorities = ["Low", "Normal", "High", "Urgent"]

    return render_template("job_new.html", clients=clients, customers=customers, assets=assets,
                           visit_types=visit_types, job_types=job_types, statuses=statuses, priorities=priorities)



@app.post("/jobs/new")
def job_create():
    internal_job_number = request.form.get("internal_job_number", "").strip()
    client_reference = request.form.get("client_reference", "").strip()
    client_id = request.form.get("client_id") or None
    customer_id = request.form.get("customer_id") or None
    asset_id = request.form.get("asset_id") or None
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
            client_id, customer_id, asset_id,
            job_type, visit_type, status, priority,
            job_address, description, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        internal_job_number, client_reference or None, display_ref,
        client_id, customer_id, asset_id,
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
def job_detail(job_id: int):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT j.*,
           c.name AS client_name, c.phone AS client_phone, c.email AS client_email, c.address AS client_address,
           cu.full_name AS customer_name, cu.phone AS customer_phone, cu.email AS customer_email, cu.dob AS customer_dob, cu.address AS customer_address,
           a.reg AS asset_reg, a.vin AS asset_vin, a.make AS asset_make, a.model AS asset_model, a.year AS asset_year
    FROM jobs j
    LEFT JOIN clients c ON c.id = j.client_id
    LEFT JOIN customers cu ON cu.id = j.customer_id
    LEFT JOIN assets a ON a.id = j.asset_id
    WHERE j.id = ?
    """, (job_id,))
    job = cur.fetchone()
    if not job:
        conn.close()
        return ("Not found", 404)

    cur.execute("""
    SELECT * FROM interactions
    WHERE job_id = ?
    ORDER BY occurred_at DESC, id DESC
    """, (job_id,))
    interactions = cur.fetchall()

    conn.close()

    statuses = ["New", "Active", "Active - Phone work only", "Suspended", "Awaiting info from client", "Completed", "Invoiced"]
    visit_types = ["New Visit", "Re-attend", "First Update", "Urgent Update", "Phone Follow-up", "Locate Only"]

    return render_template("job_detail.html", job=job, interactions=interactions, statuses=statuses, visit_types=visit_types)


@app.post("/jobs/<int:job_id>/update")
def job_update(job_id: int):
    status = request.form.get("status", "").strip()
    visit_type = request.form.get("visit_type", "").strip()
    now = datetime.now().isoformat(timespec="seconds")

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET status = ?, visit_type = ?, updated_at = ? WHERE id = ?",
                (status, visit_type, now, job_id))

    cur.execute("""
        INSERT INTO interactions (job_id, event_type, narrative, occurred_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, "Status/Visit Update", f"Status set to '{status}'. Visit type set to '{visit_type}'.", now, now))

    conn.commit()
    conn.close()
    flash("Job updated.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.post("/jobs/<int:job_id>/interactions/new")
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
def clients_list():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return render_template("clients.html", clients=rows)


@app.get("/clients/new")
def client_new():
    return render_template("client_new.html")


@app.post("/clients/new")
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
def customers_list():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers ORDER BY full_name")
    rows = cur.fetchall()
    conn.close()
    return render_template("customers.html", customers=rows)


@app.get("/customers/new")
def customer_new():
    return render_template("customer_new.html")


@app.post("/customers/new")
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
def assets_list():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM assets ORDER BY reg")
    rows = cur.fetchall()
    conn.close()
    return render_template("assets.html", assets=rows)


@app.get("/assets/new")
def asset_new():
    return render_template("asset_new.html")


@app.post("/assets/new")
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
