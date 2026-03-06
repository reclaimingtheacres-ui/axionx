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

## Queue (`/queue`)

Admin-only view, renamed from "Job Queue". Shows three live sections (no date picker):

- **Overdue** — cue_items with visit_type `Urgent: Schedule Overdue` or `Schedule Due Today`, status Pending/In Progress
- **Currently Due** — cue_items with visit_type `Schedule Due Tomorrow`, status Pending/In Progress
- **Agent Notes — Pending Review** — cue_items with visit_type `Agent Note Review`, status Pending (auto-created when an agent saves a field note)

Each row shows: × dismiss button, job number link (opens in new tab), Date/Time, Client, Borrower, Address, Action Required, and two action buttons:
- **Email** — opens a modal to compose and send an email to Client, Agent, or Both; logs a note on the job; uses SMTP
- **Update** — opens the job in a new tab

Routes: `GET /queue`, `POST /queue/send-email`, `POST /queue/<id>/dismiss`

Agent note auto-flagging: when an agent submits a field note via `POST /jobs/<id>/notes/new`, a `cue_item` with `visit_type='Agent Note Review'` is automatically created if one doesn't already exist for that job.

## Cues System

Cues (`cue_items` table) are scheduled work items attached to jobs — a date, visit type, priority, agent, and optional instructions. Agents see their cues on `/my/today`. Admins manage all cues at `/queue` and drag-and-drop assign them on `/assign`.

`auto_queue_schedule_alerts()` runs nightly (backup scheduler) and on each queue page load to create cue_items for overdue/today/tomorrow schedules.

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

## AI Update Builder (`/jobs/<id>/update-builder`)

Agents and admins can produce compliant, SWPI-style attendance updates using a guided form + OpenAI generation.

**Access**: "Create Update (AI Assist)" in the "Add to Job" dropdown (admins/both) or as a direct button (agents) on the job detail action bar. Roles `admin`, `agent`, `both` all have access.

**Workflow**:
1. Opening the builder immediately creates a `job_updates` record with `status='draft'` so nothing is lost.
2. Auto-fills: job reference, client, customer, address, customer mobile.
3. Agent fills minimum facts using toggles: attendance type (first/re), property description (first only), security sighted, calling card, call outcome + voicemail, SMS, neighbour outcome. **Phone number used** field appears when call or SMS is toggled on (auto-fills from customer mobile, editable).
4. "Generate Update" POSTs to `/jobs/<id>/update-builder/generate`, calls OpenAI (gpt-4o-mini), returns full SWPI-style narrative (third person, British spelling, no acronyms, required calling-card wording, points-of-contact line, ETA).
5. Narrative appears in editable textarea; agent can adjust before saving.
6. "Save Update to Job" POSTs to `/jobs/<id>/update-builder/save` — persists to `job_field_notes` tagged `[AI Update]`, marks draft `complete`, clears both "Update Required" and "Complete Attendance Update" cues.
7. **Address validation**: if job has no address, Generate button is disabled and an alert is shown.
8. **Auto-save on exit**: JS sends `sendBeacon` to `/autosave?leaving=1` on `beforeunload`, plus periodic 30s autosave. On exit (leaving=1), a High-priority `cue_item` ("Complete Attendance Update") is created for the agent.
9. **Draft banner**: agents (role=agent/both) see an amber banner on every page when they have pending drafts. Clicking it goes to `/my/drafts`.
10. **My Today**: pending drafts surfaced at the top with resume links.
11. **My Drafts** (`/my/drafts`): dedicated page listing all open drafts.

**Points of contact rule (updated)**: calling card = 1pt, telephone call made = 1pt (any outcome), SMS sent = 1pt. Max 3pts. ETA = 2 days excl. Sundays for 1-2 POC; 8 days excl. Sundays for 3 POC.

**Narrative format**: Opening sentence is constructed server-side: `dd/mm/yy at h:mma Our agent [re-]attended at [address][, finding a {prop_desc}].` AI assembles the prose paragraph around fixed-wording sentences (calling card, security, phone, SMS).

**Routes**:
- `GET /jobs/<id>/update-builder` — open/resume draft
- `POST /jobs/<id>/update-builder/generate` — AI narrative generation (JSON API)
- `POST /jobs/<id>/update-builder/save` — save final update (JSON API)
- `POST /jobs/<id>/update-builder/autosave` — background form-state save; `?leaving=1` also creates cue
- `GET /jobs/<id>/update-builder/draft-check` — check if draft exists (JSON API)
- `GET /my/drafts` — agent's list of all pending drafts

**DB additions**:
- `job_updates` — full structured record per update (draft/complete status, all inputs, generated + final narrative, tokens used)
- `ai_usage_log` — per-generation log: user, job, model, tokens, key source
- `jobs.is_regional`, `jobs.confirmed_skip` — flags used in narrative context
- `system_settings.openai_api_key`, `system_settings.ai_use_own_key` — admin-configurable AI key fallback
- `cue_items.cue_link` — direct URL stored on cue (used for draft resume links)

**Admin Settings > AI Settings tab**:
- Toggle to use own OpenAI API key instead of Replit AI credits
- AI usage log table (last 50 uses): timestamp, user, job, feature, tokens, key source

**AI Integration**: Uses Replit's built-in OpenAI access via `AI_INTEGRATIONS_OPENAI_BASE_URL` + `AI_INTEGRATIONS_OPENAI_API_KEY` env vars (no separate key required by default). Admin can switch to own key via settings.

## Geomap (`/map`)

Admin-only full-page map view combining job pins and live agent location tracking.

**Left panel** (250px):
- Job status filter toggle buttons: ALL | Active | New | Pending (multi-select, synced with map)
- Live job count badge
- Agents list with colour-coded status dots: green (<5 min), yellow (5–30 min), grey (no data / >30 min)
- Clicking an agent row pans the map to their position

**Map** (Google Maps, rest of screen):
- Job pins coloured by status: Active=blue, New=green, Pending=orange
- Jobs without cached lat/lng are geocoded client-side (Geocoder API); result cached via `POST /api/jobs/<id>/geocode`
- Clicking a pin shows an info window with job ref (linked), customer, client, status, address, agent
- Agent positions shown as purple initials circles; polled every 30 s via `GET /api/map/data`

**Agent tracking** (`/my/today`):
- Agents' browser silently requests GPS on page load, re-sends every 60 s via `POST /api/agent/location`
- A subtle green "Location sharing" badge appears at the bottom-right once GPS is obtained
- No error shown if geolocation is denied

**Routes**:
- `GET /map` (admin) — renders map.html
- `GET /api/map/data` (admin) — JSON of active/pending/new jobs with addresses, cached lat/lng, and agent positions (2-hr window)
- `POST /api/agent/location` (any logged-in user) — upserts agent position
- `POST /api/jobs/<id>/geocode` (any logged-in user) — caches geocoded lat/lng

**DB additions**:
- `jobs.lat`, `jobs.lng` REAL columns (geocode cache)
- `agent_locations` table: `user_id UNIQUE, lat, lng, accuracy, updated_at`

**Template block**: `layout.html` now exposes `{% block scripts %}` between the `initGoogleMaps` definition and the Maps `<script src>` tag — child templates can safely override/wrap `window.initGoogleMaps` here.
