# Axion Prototype

## Overview
Axion Prototype is a Flask-based field operations management application designed to streamline field operations, improve job dispatching, and enhance agent productivity. It focuses on efficient tracking of jobs, clients, customers, assets, cues, and staff. Key capabilities include comprehensive job management, role-based access, a dynamic queueing system, audit logging, monthly reporting, and robust field resource management. The system also integrates a Licence Plate Recognition (LPR) system with real-time plate lookups, watchlist hits, agent dispatch, and AI/ML-driven predictive patrol intelligence to identify high-opportunity patrol areas and automate dispatch processes. The project emphasizes mobile accessibility and data-driven decision-making.

## User Preferences / Development Guidelines
- Every change request must be reviewed for full workflow impact across web, mobile, queue logic, scheduling, and data consistency — not limited to visible UI edits.
- Proactively include: smarter defaults, fewer user clicks, better persistence of user inputs, clearer validation, improved information visibility, and cross-platform consistency (web + mobile).
- AxionX is an operational field and office platform. Prioritise: speed for field agents, minimal admin repetition, clear information hierarchy, consistent behaviour across web and mobile, automation wherever possible.
- If a feature can be made more efficient or powerful without breaking existing workflows, implement the improvement and document the change.

## System Architecture

### Core Technologies
- **Backend**: Python 3.11 with Flask 3.0.3
- **Database**: SQLite (`axion.db`)
- **Frontend**: Jinja2 templates, Bootstrap 5.3.3, and custom JavaScript.
- **Mobile Wrapper**: Native iOS application (SwiftUI, WKWebView) for mobile web routes.

### Design Patterns & Features

**1. Role-Based Access Control:** Differentiates 'Admin' and 'Agent' roles with tailored access to features like job visibility, dashboards, cues, assignment boards, reports, and user management.

**2. Dynamic Queue System:** Provides an admin-only view with 'Agent Notes – Pending Review' pinned at the top (hidden when empty, sorted by most recently updated), followed by 'Overdue' and 'Currently Due' sections. When a job is rescheduled or updated, its cue items are auto-completed and the queue view refreshes automatically on tab focus via `/queue/active-cue-ids` polling. Direct email composition and job updates available inline.

**2a. Job Scheduling (Booking Type Combobox):** All booking type fields across the system (job detail inline form, schedule prompt modal, add bookings modal, new job form) use a unified searchable combobox with type-to-search, type-to-select, and create-new behaviour. Recently used types appear at the top with a "recent" label. New types are saved via `/booking-type/ajax` with case/spacing normalization to prevent duplicates. After saving a booking, users remain on the same page (AJAX submission) with a success message — no redirect to Jobs or other screens.

**2b. Job List (Web — Sorting, Pagination, Sticky Header):**
- Default sort: **Oldest Scheduled** — overdue jobs first, then earliest upcoming, then unscheduled. The `next_scheduled` subquery includes all pending schedules (not just future ones), so overdue dates surface at the top.
- Server-side **pagination**: 25 jobs per page (configurable 25/50/100 via dropdown). Count query + LIMIT/OFFSET.
- **Sticky header**: Jobs heading, search, status filter, sort, more filters, and filter button stay fixed at the top while scrolling, with a subtle background.
- **Single operational date**: Only `next_scheduled` is shown in the job row (as a badge). Overdue dates are highlighted in red with "OVERDUE" prefix. The `updated_at` date has been removed from the list to avoid confusion.
- Sort options: Oldest Scheduled (default), Active first, Agent A–Z, Job # high–low, Client ref high–low.

**2c. Job List (Mobile — Distance Default):**
- Mobile app defaults to **Distance – Nearest First** sorting when GPS is available.
- If GPS permission is denied, falls back to Visit Date sort with a warning banner.
- Distance calculated client-side using Haversine formula with server-assisted batch geocoding for missing coordinates.

**2d. Add Client Workflow (Import Repair):**
- Dedicated **Add Client modal** (`#addClientModal`) for linking a missing client to a job — separate from Edit Job.
- AJAX-based `POST /jobs/<id>/link-client` route: links existing client or creates and links new client in a single transaction with audit logging.
- Smart suggestions: if the imported job has a `lender_name`, the search field pre-fills it so likely client matches appear immediately.
- Inline client card update after save — no page reload. Success confirmation shown in place.
- Button states: **Add Client** (when no client), **Edit** + **Change** (when client exists). Edit Client and Change Client are separate workflows.
- Null-safe handling in Edit Job route: `customer_id` safely parsed, `job_type`/`visit_type`/`status`/`priority` default to safe values if missing (fixes Internal Server Error on imported jobs).

**2e. Schedule Calendar (Web):**
- Full calendar-based schedule view replacing the old "next 30 days" table.
- **Views**: Day (default for agents), Week (default for admin), Month, Agenda/List — all toggled via toolbar buttons.
- **Date navigation**: Date picker, Today button, Previous/Next arrows. All view changes are AJAX-driven (no full page reload).
- **Admin agent filter**: Dropdown to view All Agents, specific agent, or Unassigned. Colour-coded bookings by agent when "All Agents" is selected.
- **Agent default**: Non-admin users see only their own bookings (forced server-side).
- **Past/Upcoming/All filter**: Toggle to view historical bookings, upcoming only, or all.
- **Booking cards**: Show time, job ref, customer name, booking type, address snippet, status badge. Click opens popup preview with full details.
- **Quick actions from popup**: Open Job, Reschedule (with datetime picker), Mark Complete, Cancel — all via AJAX with booking history tracking.
- **API**: `GET /schedule/api/events?start=&end=&agent_id=&status_filter=` returns JSON events for the requested range. Lazy-loaded by visible date range only.
- **Booking history**: `schedule_history` table tracks all mutations (created, rescheduled, cancelled, completed) with old/new state, changed_by, and notes. Preserves original schedule entries even after changes.
- **Quick action endpoints**: `POST /schedule/api/<id>/reschedule`, `POST /schedule/api/<id>/complete`, `POST /schedule/api/<id>/cancel`.

**3. Cues System:** Manages `cue_items` (scheduled tasks) with properties like date, visit type, priority, and agent assignment. Supports daily cue access for agents and drag-and-drop assignment for admins, with automatic cue generation for overdue or upcoming schedules.

**4. Audit Log:** Logs all significant system actions, accessible via the admin dashboard.

**5. Field Resources Management:** Centralized management of Tow Operators and Auction Yards with interactive modals for adding, editing, and deleting entries.

**6. Forms Module:** Grid-based dashboard for 7 active form types (SWPI VIR, Transport Instructions, Voluntary Surrender, Form 13, Wise VIR, Auction Letter, Tow Letter). Forms are editable HTML with pre-populated fields saving to DB before PDF generation via ReportLab. Signatures captured live via canvas pads — NOT stored in DB. After every PDF is generated, it is auto-saved to job_documents and a note added to job_field_notes. Filename format: "[JobNumber] - [Form Name] - [DD-MM-YYYY].pdf". Complete Repo Pack (GET) merges unsigned reference copies and also attaches to the job.

**7. Job Creation Enhancements:** Improved job creation flow with client job number tracking, reference search, and a "Clone" functionality for pre-filling new job forms.

**8. CSV Job Import:** Allows bulk import of job data via CSV files, with duplicate handling.

**8a. Duplicate Finder (Settings):** Two-mode duplicate detection tool on the Settings page (2nd tab position):
- **Database Scan:** Finds duplicate jobs (by job number or account number) and duplicate clients (by name) already in the system.
- **CSV File Scan:** Multi-file upload (accepts multiple CSVs at once) checks for duplicates within the selected files and against existing database records before import.
- All delete operations use AJAX (`/admin/api/duplicates/delete-job`, `/admin/api/duplicates/delete-client`) so users stay on the Settings page — no redirect to Jobs or Clients lists.
- Summary bar shows file count, total records scanned, and duplicate count after each scan.

**9. AI Update Builder:** Guided form using OpenAI (gpt-4o-mini) to generate SWPI-style attendance updates, featuring auto-filling, fact toggles, AI narrative generation, editable output, and address validation.

**10. Geomap & Agent Tracking:** Admin-only map view displaying job pins by status and live agent locations, with client-side geocoding and opt-in GPS tracking for agents.

**11. Licence Plate Recognition (LPR) System:**
    - **Offline Queue & Background Sync:** Robust offline data capture and background synchronization for sightings.
    - **Push Notifications & Dispatch:** APNs integration for real-time alerts on watchlist hits, escalated sightings, and proximity alerts. Includes dispatch intelligence for calculating distances, ETAs, and recommending agents.
    - **Map Upgrade:** Leaflet.markercluster for enhanced visualization of sightings.
    - **Passive Background Location:** iOS `AgentLocationService` for battery-efficient location tracking.
    - **Route/ETA Intelligence & Native Dispatch:** Integrates `DispatchManager` in iOS for managing follow-ups, geofencing, and ETA-ranked agent recommendations.
    - **Patrol Intelligence:** Automated ranking of plates by patrol opportunity confidence using historical sightings and ML-assisted predictions.
    - **Closed-Loop Learning:** Captures and analyzes prediction-versus-outcome history for continuous improvement.
    - **Adaptive Ranking Config & A/B Experiment Framework:** Supports dynamic adjustment of ML/rule weighting and controlled experiments for LPR features.
    - **Policy Engine & Controlled Automation:** Defines rules for automated decision-making and actions, with safeguards and post-change monitoring.
    - **Document Upload / Import Workflow (Web Only):** Extracts data from `.docx`, `.pdf`, `.doc` files for autofilling job creation forms, including specific parsing for "Wise Group" cases.
    - **Floating LPR FAB (Multi-step inline sheet):** Persistent FAB on all mobile screens opens a 3-step sheet: (1) action chooser with Patrol Mode featured + Live Scan / Take Photo / Manual Entry / Patrol Intel grid, (2) inline plate entry with JSON lookup, (3) full result display with Save Sighting — no navigation away from current screen. `window.handleNativePlateScan` defined globally for iOS bridge.
    - **Patrol Mode (`/m/lpr/patrol-mode`):** Full-screen live camera continuous scanning mode. Captures frames every 2.5s via `getUserMedia`+canvas, POSTs to `POST /m/api/lpr/patrol-scan` (Tesseract OCR → allocation lookup), 30s client-side duplicate suppression per plate. Shows status overlay, viewfinder, live plate feed, torch control. On allocated/restricted/watchlist match: high-visibility alert with haptic feedback, Open Job / Contact Office / Save Sighting (with GPS) / Continue Scanning. Manual plate entry within patrol mode. Stop Patrol returns to jobs. Feature flag: `system_settings.lpr_patrol_mode_enabled` (default 1).

**13. Quick Field Notes (Mobile):** Rich note-taking from job detail screen. Backend: `note_type` + `audio_filename` columns on `job_field_notes`; `POST /m/job/<id>/quick-note` (multipart text/audio/photo); `GET /m/note-audio/<note_id>`, `GET /m/note-photo/<file_id>` serving routes. Notes tab: type icon pills, photo thumbnails with lightbox, inline audio players, agent/timestamp. Add Note bottom sheet: text, MediaRecorder voice (pulsing indicator, 3-min limit), camera/gallery photo; live-injects new note card without page reload.

**12. Repo Lock (v2):** Per-security-item repossession record accessible on desktop and mobile. Features draft saving and submission workflows, generating formatted notes and linking to PDF generation for VIR, Transport Instructions, and other forms. Includes signature capture and PDF generation via `pdf_gen.py`.

**14. Internal Messaging System:** Staff messaging (admin↔agent, agent↔agent) with job-linked and direct conversations.
- Tables: `conversations` (type: direct|job, optional job_id), `conversation_participants`, `messages`, `message_reads`
- Desktop: Two-panel layout at `/messages` and `/messages/<conv_id>`. Left sidebar = conversation list; right = chat bubbles. Reply with Enter key or Send button.
- Mobile: Full-screen conversation list at `/m/messages`; chat interface at `/m/messages/<conv_id>` with pinned reply bar.
- New message modal (desktop) + compose sheet (mobile): select recipient, optional job link, first message body.
- Unread badge: blue count badge in desktop sidebar nav + dot indicator on mobile "Msgs" tab. Both poll `/api/messages/unread-count` every 30 seconds. Desktop shows a toast notification when new messages arrive.
- Job-linked conversations show a yellow banner with clickable link to the job.
- Shared API: `GET /api/messages/unread-count`, `POST /messages/<conv_id>/read`

**15. Customer Call/SMS Actions:**
- `customer_detail.html`: Phone numbers show inline Call (green) + SMS (blue) buttons with `tel:` and `sms:` schemes.
- `job_detail.html`: Linked customer rows show primary phone with Call + SMS buttons. Client phone shows Call button.
- Mobile: Already had Call/SMS on job detail; now consistent across all platforms.

## External Dependencies

- **Database**: SQLite
- **Frontend Libraries**: Bootstrap 5.3.3, Google Maps API, Leaflet.js, Leaflet.markercluster
- **Backend Libraries**: Flask, `python-docx`, `pypdf`, `httpx[http2]`, `PyJWT`, `antiword` (external binary)
- **AI Services**: OpenAI (gpt-4o-mini), Apple Core ML
- **Mobile-Specific (iOS)**: WKWebView, SwiftUI, CoreLocation, NWPathMonitor, UNUserNotificationCenter, BackgroundTasks, MapKit