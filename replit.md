# Axion Prototype

A Flask-based field operations management app for tracking jobs, clients, customers, assets, cues, and staff.

## Stack

- **Backend**: Python 3.11 + Flask 3.0.3
- **Database**: SQLite (`axion.db`)
- **Frontend**: Jinja2 templates + Bootstrap 5.3.3 (CDN)

## Running

Workflow: `python app.py` on port 5000.

## Default Login

- **Email**: `admin@axion.local`
- **Password**: `Admin1234`

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
  (job items are managed inline in job_detail.html)
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
- **job_items** — items linked to a job (vehicle, property, equipment, other)
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

## Field Resources (`/resources`)

Available to all logged-in users (admin + agent) via sidebar. Two sections:
- **Tow Operators** — company name, phone, address; add/edit/delete via popup modals (fetch-based, no page reload)
- **Auction Yards** — yard name, address; same popup pattern

Routes: `GET /resources`, `POST /resources/tow-operators/add|/<id>/edit|/<id>/delete`, `POST /resources/auction-yards/add|/<id>/edit|/<id>/delete`

DB tables: `tow_operators`, `auction_yards`

## Forms Tab (Job Detail)

Each job's detail page has a "Forms" tab (visible to all users) containing:
- **6 pre-defined forms** — Worksheet, VIR, Vehicle Inspection Report), Form 13, Transport Instructions, Repossession Lock, Termination Notice
- Each form opens as a Bootstrap modal with a print-ready A4 layout, auto-populated from job data; editable fields use `contenteditable`; date/time fields auto-fill with current date/time
- Transport Instructions includes dropdowns for Tow Operator and Auction Yard (populated from DB)
- **Admin-only**: "Create Form" card that opens a builder modal — select fields from a static list, name the template, save. Custom templates appear as cards and open a print modal showing selected job fields
- `@media print` CSS hides the shell and shows only `.form-print-area`

Routes: `POST /form-templates/add`, `POST /form-templates/<id>/delete`  
DB table: `form_templates` (name, field_list JSON, created_by, active)

## Create Job Enhancements

- **Client Job Number** field (`jobs.client_job_number`) saved alongside client reference; "Same as reference" checkbox mirrors the reference value live.
- **Reference search bar** on `/jobs/new`: type 2+ chars to search existing jobs by `client_reference` or `client_job_number` via `GET /jobs/search-reference?q=`.
- **Clone modal**: clicking a search result opens a detail popup via `GET /jobs/<id>/clone-data`; the Clone button fills the entire new-job form (client, customer, addresses, assets, all fields) while keeping the next auto-generated job number.

## CSV Import (`/import/jobs`)

Upload CSV with columns: `InternalJobNumber, ClientReference, JobType, VisitType, Status, Priority, JobAddress, Description`. Duplicate InternalJobNumbers are skipped.
