# Axion Prototype

A Flask-based field operations management app for tracking jobs, clients, customers, assets, cues, and staff.

## Stack

- **Backend**: Python 3.11 + Flask 3.0.3
- **Database**: SQLite (`axion.db`)
- **Frontend**: Jinja2 templates + Bootstrap 5.3.3 (CDN)

## Running

Workflow: `python app.py` on port 5000.

## Default Login

A seed admin is created on first run if no users exist:
- **Email**: `admin@axion.local`
- **Password**: `admin`

## Structure

```
app.py
templates/
  login.html            Standalone login page
  layout.html           Base template (navbar adapts by role)
  index.html            Dashboard counts
  jobs.html / job_new.html / job_detail.html
  clients.html / client_new.html
  customers.html / customer_new.html
  assets.html / asset_new.html
  users.html / user_new.html          Admin only
  admin.html                          Admin dashboard
  cues.html                           Cue management (admin)
  assign.html                         Drag-drop assignment board (admin)
  report_monthly.html                 Monthly report (admin)
  my_today.html                       Agent daily cue view
  import_jobs.html                    CSV import (admin)
```

## Database Schema

- **users** — staff (admin / agent roles)
- **clients** — companies/creditors
- **customers** — debtors/subjects
- **assets** — vehicles
- **jobs** — core entity with internal_job_number, client_reference, display_ref, assigned_user_id
- **interactions** — timestamped job timeline entries
- **cue_items** — scheduled field visits/tasks per job (due date, visit type, priority, assignment, status)
- **audit_log** — all significant actions logged with actor, entity, action, message

## Role-based Navigation

| Feature | Admin | Agent |
|---|---|---|
| Jobs (all) | ✓ | own only |
| Dashboard | ✓ | — |
| Cues | ✓ | — |
| Assign Board | ✓ | — |
| Reports | ✓ | — |
| Users | ✓ | — |
| Import | ✓ | — |
| My Today | — | ✓ |

## Cues System

Cues are scheduled work items attached to jobs — a date, visit type, priority, agent, and optional instructions. Agents see their cues on `/my/today`. Admins manage all cues at `/cues` and drag-and-drop assign them on `/assign`.

## Audit Log

Every cue create, assign, status change, and user action is written to `audit_log`. The admin dashboard shows the last 20 entries.

## Monthly Report (`/reports/monthly`)

Filter by YYMM prefix (e.g. `2602`). Shows total jobs, jobs by status, and completed cues per agent for the month.

## CSV Import (`/import/jobs`)

Upload CSV with columns: `InternalJobNumber, ClientReference, JobType, VisitType, Status, Priority, JobAddress, Description`. Duplicate InternalJobNumbers are skipped.
