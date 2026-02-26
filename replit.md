# Axion Prototype

A Flask-based field operations management app for tracking jobs, clients, customers, and assets, with staff login and role-based access.

## Stack

- **Backend**: Python 3.11 + Flask 3.0.3
- **Database**: SQLite (`axion.db`)
- **Frontend**: Jinja2 templates + Bootstrap 5.3.3 (CDN)

## Running

The app runs via the "Start application" workflow: `python app.py` on port 5000.

## Default Login

A seed admin account is created automatically on first run if no users exist:
- **Email**: `admin@axion.local`
- **Password**: `admin`

Change this immediately via the Users section after first login.

## Structure

```
app.py                  # Flask app — all routes, DB logic, auth
templates/
  login.html            # Login page (standalone, no navbar)
  layout.html           # Base template with navbar, flash messages, user info
  index.html            # Dashboard with counts
  jobs.html             # Job list with search/filter + assigned agent
  job_new.html          # New job form (includes assign-to dropdown)
  job_detail.html       # Job detail, update status/visit/assignment, timeline
  clients.html          # Client list
  client_new.html       # New client form
  customers.html        # Customer list
  customer_new.html     # New customer form
  assets.html           # Asset list
  asset_new.html        # New asset form
  users.html            # User list (admin only)
  user_new.html         # New user form (admin only)
  import_jobs.html      # CSV import for jobs (admin only)
axion.db                # SQLite database (auto-created on first run)
requirements.txt        # Python dependencies
```

## Database Schema

- **users** — staff accounts (admin / agent roles)
- **clients** — companies/creditors who assign jobs
- **customers** — debtors/subjects of jobs
- **assets** — vehicles (reg, VIN, make, model, year)
- **jobs** — core entity; stores internal_job_number, client_reference, display_ref, and assigned_user_id
- **interactions** — timestamped timeline entries per job

## Auth & Role Logic

- All routes (except `/login`) require login via `@login_required`
- Admin users see all jobs; agents only see jobs assigned to them
- Users, Import routes are `@admin_required`
- Job detail enforces agent can only view their assigned jobs

## CSV Import (Jobs)

Upload a CSV at `/import/jobs` (admin only). Expected columns:
`InternalJobNumber, ClientReference, JobType, VisitType, Status, Priority, JobAddress, Description`

Rows with duplicate `InternalJobNumber` are skipped.
