# Axion Prototype

A Flask-based field operations management app for tracking jobs, clients, customers, and assets.

## Stack

- **Backend**: Python 3.11 + Flask 3.0.3
- **Database**: SQLite (`axion.db`)
- **Frontend**: Jinja2 templates + Bootstrap 5.3.3 (CDN)

## Running

The app runs via the "Start application" workflow: `python app.py` on port 5000.

## Structure

```
app.py                  # Flask app, all routes and DB logic
templates/
  layout.html           # Base template with navbar and flash messages
  index.html            # Dashboard with counts
  jobs.html             # Job list with search/filter
  job_new.html          # New job form
  job_detail.html       # Job detail, status update, interaction timeline
  clients.html          # Client list
  client_new.html       # New client form
  customers.html        # Customer list
  customer_new.html     # New customer form
  assets.html           # Asset list
  asset_new.html        # New asset form
axion.db                # SQLite database (auto-created on first run)
requirements.txt        # Python dependencies
```

## Database Schema

- **clients** — companies/creditors who assign jobs
- **customers** — debtors/subjects of jobs
- **assets** — vehicles (reg, VIN, make, model, year)
- **jobs** — core entity linking client, customer, asset; has status, priority, job type, visit type, address
- **interactions** — timestamped timeline entries on a job (calls, attendances, notes, etc.)

## Features

- Dashboard with counts of all entity types
- Jobs: create, list (with status/text filter), detail view
- Job status and visit type quick-update
- Interaction/timeline log per job (Attendance, Call, SMS, Email, Card Left, Neighbour Interview, Repo Attempt, Note)
- Clients, Customers, Assets: create and list
- Google Maps link for job addresses
