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
- **Agent Draft Lockout**: Agents with 5+ unfinished attendance update drafts are blocked from accessing Jobs list, Job detail, My Today, and mobile Schedule/Jobs pages — redirected to `/my/drafts`. At 4 drafts, the banner flashes amber with a warning that access will be restricted at 5. At 5+, the banner turns red. Update-builder remains accessible so agents can complete their drafts. `DRAFT_LOCKOUT_THRESHOLD = 5` constant in `app.py`. Only applies to `role == 'agent'`, not admin/both.

**2. Dynamic Queue System:** Provides an admin-only view with 'Agent Notes – Pending Review' pinned at the top (hidden when empty, sorted by most recently updated), followed by 'Overdue' and 'Currently Due' sections. When a job is rescheduled or updated, its cue items are auto-completed and the queue view refreshes automatically on tab focus via `/queue/active-cue-ids` polling. Direct email composition and job updates available inline.
- **Agent ID column**: Every queue row shows the assigned agent as a styled badge (blue for assigned, amber for unassigned).
- **Queue Summary bar**: Live counts at top showing Total Jobs, per-Agent counts, and per-Client counts. Each count chip is clickable and acts as a one-click filter. Summary updates automatically as items are dismissed or filtered.
- **Queue filters**: Agent dropdown (All Agents / specific agent / Unassigned), Client dropdown (All Clients / specific client), and a free-text search field (job #, customer name, address). Filters combine independently. Clear Filters button resets all. Active filters also apply to the email-queue function.
- **Email Queue to Agent**: `POST /queue/email-agent-queue` sends a clean HTML table of the agent's entire queue. Respects active client filter. Email includes job ref, client, borrower, address, status, and action required — grouped by section (Overdue / Currently Due / Agent Notes). Accessible via "Email Queue to Agent" button next to the summary bar.
- Routes: `POST /queue/email-agent-queue`.

**2a. Job Scheduling (Booking Type Combobox):** All booking type fields across the system (job detail inline form, schedule prompt modal, add bookings modal, new job form) use a unified searchable combobox with type-to-search, type-to-select, and create-new behaviour. Recently used types appear at the top with a "recent" label. New types are saved via `/booking-type/ajax` with case/spacing normalization to prevent duplicates. After saving a booking, users remain on the same page (AJAX submission) with a success message — no redirect to Jobs or other screens.

**2b. Job List (Web — Streamlined List Layout):**
- **Streamlined list design (Design C)**: Compact rows with a coloured status bar on the left edge. Each row shows job ref + customer on line one, client/reg/job-type on line two. Right side: agent name, schedule date, booking pill, and status dropdown (admin) or pill (agent).
- Default sort: **Oldest Scheduled** — overdue jobs first, then earliest upcoming, then unscheduled. The `next_scheduled` subquery includes all pending schedules (not just future ones), so overdue dates surface at the top.
- Server-side **pagination**: 25 jobs per page (configurable 25/50/100 via dropdown). Count query + LIMIT/OFFSET.
- **Sticky header**: Jobs heading, search, status filter, sort, more filters, per-page selector, and result count stay fixed at the top while scrolling.
- Full-row click navigates to job detail. Interactive controls (status dropdown, Update Emailed button) use event delegation to avoid conflict with row navigation.
- **Edge cases handled**: "No client", "Unassigned" (red), "No schedule", "No booking" all shown explicitly.
- Sort options: Oldest Scheduled (default), Active first, Agent A–Z, Job # high–low, Client ref high–low.

**2b2. Job Detail (Web — Side Panel Layout / Design B):**
- **Compact header**: Page title shows job ref + customer (from layout.html `block page_title`). Action bar row with blue dropdown buttons (Add to Job, Create Document, Copy, Send Message, Add Bookings) on the left, status pill on the right. Admin gets editable status select; agents get read-only badge.
- **Compact info row** (sub-XL only): Shows job type · visit · priority · internal # · assigned agent · next schedule date — visible when the right sidebar is hidden.
- **Tab navigation**: Job | Notes & Docs | Schedule | Forms | Settings (admin only). Same tab structure as before.
- **Right sidebar** (280px, XL+ only): Persistent panel with Job Info (type, visit, priority, internal #, client ref), Assigned agent (avatar + name), Schedule (next booking date/time/type), Financial (payments received, count), Activity (notes/docs/bookings counts). Sidebar scrolls independently from main content.
- **Flex layout**: Outer flex container with overflow hidden; tab content and sidebar each have independent `overflow-y:auto`. Archive/Cold Store banners remain above the action bar.

**2b3. New Job Form (Web — Two-Column Single Page / Design B):**
- **Single-page layout**: No more modal with tabs. All fields visible on one scrollable page.
- **Two-column grid** (lg+): Left column has Job ID, Client & Customer, Classification, Security/Asset cards. Right column (380px, sticky) has Lender & Financial, Instructions, Schedule cards plus Save/Cancel buttons.
- **Auto-parsed vehicle details**: Year/Make/Model/Colour/Engine fields are hidden inputs, auto-parsed from the Description field via `parseDesc()` bidirectional sync. Collapsible "Auto-parsed details" toggle shows parsed values as read-only display.
- **Address sync**: Customer address auto-populates Job Address (checkbox "Use customer address") and Asset Address (checkbox "Use customer address" in Security card header).
- **Contract→Account sync**: Contract Number auto-populates Account Number field until user manually edits it.
- **Auto-save drafts**: Client-side localStorage draft system. Saves every 10 seconds, shows "Draft saved Xs ago" indicator bar. Drafts auto-restore on page load (unless autofill/new entity redirect). "Discard draft" button clears saved data.
- **Clone from reference**: Typing in Contract Number triggers search typeahead, selecting a result opens Clone modal to pre-fill form from existing job.
- **Action buttons**: "Save Job" (primary submit), "Save & Add Another" (submits then redirects back with lender prefill), "Cancel" (back to jobs list).
- **Entity creation**: "+ New" buttons for Client, Customer, Agent open popup modals for inline creation without leaving the form.
- **Booking type combobox**: Schedule section uses searchable combobox with recent types, type-to-create capability.
- **Agent Recommendation Popup**: After creating a new job with an address and no agent assigned, an "Agent Recommendation" modal automatically appears. It extracts the 4-digit postcode from the job address and queries for active agents who have active jobs with pending schedules in the same postcode area. Each suggestion shows agent name, job count in the area, and job refs — with a one-click "Assign" button. Skippable via "Skip" button. Routes: `GET /api/agent-recommend/<job_id>`, `POST /jobs/<job_id>/assign`.
- **Autofill post-save flow**: When a job is created via document upload, the instruction document is automatically saved as both a `job_documents` record (type: Instruction) and a `job_field_notes` entry with the file attached (separate blob copy to avoid deletion coupling). After save, the user is redirected to the job detail Notes tab with the Add Note modal open so they can immediately add email notes or additional documents.

**2c. Job List (Mobile — Distance Default + Search):**
- Mobile app defaults to **Distance – Nearest First** sorting when GPS is available.
- If GPS permission is denied, falls back to Visit Date sort with a warning banner.
- Distance calculated client-side using Haversine formula with server-assisted batch geocoding for missing coordinates. Distance unit (km/mi) selection updates labels immediately when changed in filter sheet.
- **Background geocoding**: `backup_scheduler.py` runs geocode batches every 10 minutes (100 jobs per batch, newest first, using Google Geocoding API). Jobs that fail geocoding 3 times are skipped (`geocode_fail` column). Client-side geocoder sends specific visible job IDs for targeted geocoding, tracks sent IDs to avoid duplicate requests. Google API key from `GOOGLE_MAPS_API_KEY` env var.
- **Search**: Search icon positioned right-aligned in input. Client-side filter checks ref (display_ref, internal_job_number, client_reference, account_number), customer, address, reg, vin, lender. When query ≥ 2 chars, a debounced server-side search (`GET /m/api/jobs/search?q=`) fetches additional results beyond the 300-job client-side cap, appended below a "additional results from full search" banner. Server search covers all reference fields plus client_job_number. When a search query (`q`) is active, scope/completed/status filters are bypassed so matching jobs are always found.
- **Assigned agent** (admin view): Each job card shows the assigned agent name below the metadata row when logged in as admin.

**2c2. Job Detail (Mobile — Panel Order):**
- **Panel order**: Customer → Vehicle Details → Financial Details → Client → Description & Instructions.
- **Customer card**: Shows customer name, assigned agent (admin view), clickable address (opens navigation chooser with Waze/Google Maps/Apple Maps), phone (tap for call/SMS/WhatsApp), email, account number with inline REGULATED/UNREGULATED badge.
- **Regulation badge colors**: REGULATED = red (#fee2e2/#b91c1c), UNREGULATED = green (#dcfce7/#166534).
- **Address navigation**: Address text is tappable (blue, with map icon) and opens the navigation chooser directly. No separate Directions quick-action button.
- **Quick-action bar removed**: REG/VIN/DIRECTIONS buttons removed from the top of the detail tab. REG and VIN info remain in the Vehicle Details card.
- **Doc viewer close button**: Enlarged tap target (36×36px min, visible gray background, rounded corners) for reliable iOS touch interaction.

**2c3. Job Pins Map (Mobile):**
- Route `/m/map` with `m_map()` handler. Accessible from the "Map" tab in the bottom nav bar.
- Uses **Leaflet.js** with OpenStreetMap tiles (free, no API key required). Replaces prior Google Maps dependency.
- **Colored pin markers** by job status: green (Active/New/In Progress/Ready), amber (Pending/Hold/Instructed/Awaiting), red (Suspended/Cancelled/Overdue), gray (others). Pins are drop-pin shaped SVGs with white inner circle.
- **Agent vs Admin scope**: Agents see only their assigned jobs; admins see all jobs. Admin view shows assigned agent name in popup and job list cards.
- **Date filter pills**: Today, Tomorrow, Week, Month, All (default). Fetches from `/m/api/map/jobs?date_filter=<filter>`.
- **Job list below map** (GeoOp-style): Sorted by distance from agent (if GPS available). Each card is a tappable row linking to job detail, with: colored left bar matching status, full status text label in color, customer name + client name as bold title, detail line (job type - customer - client), due date and agent (admin), distance top-right in blue, note count badge bottom-right (blue ≤10, amber 11–20, red 21+), right chevron. No separate action buttons.
- **GPS tracking**: Agent location shown as blue circle marker. Auto-updates based on user GPS preferences. My-location button recentres map.
- **Popup on pin tap**: Shows job ref, customer, lender, address, distance, due date, agent (admin only). Action buttons: Open Job, Navigate.
- **Filter sheet** (iOS-style): Triggered by "Filter" button in date pill bar. Bottom sheet with Cancel/Done header, iOS-style segmented controls for: Job Type (Scheduled/Unscheduled/All), Job Assignment Filter (Mine/Everyone — admin only), Show Completed Jobs for (Day/Week/Month/All), Display Jobs by (Visit Date/Status/Distance/Creation Date), Sorting Order (Ascending/Descending). Applied client-side to both map pins and job list. Filter button highlights blue when non-default filters are active.
- Template: `templates/mobile/map.html`. API: `m_api_map_jobs()` at `/m/api/map/jobs`.

**2c-ii. Mobile Jobs List (`/m/jobs`):**
- GeoOp-style job cards with: colored left status bar, customer name (bold), address, job ref with client reference, colored status label (matching bar color), due date, asset reg, distance (blue, GPS-dependent), note count badge (blue ≤10, amber 11–20, red 21+), right chevron, agent name (admin only).
- Query includes `note_count` from `job_field_notes` table.
- Template: `templates/mobile/jobs.html`. Query: `_mobile_jobs_query()` shared function.

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
- **Hover preview**: Desktop hover shows a dark tooltip with job ref, customer, booking type, agent, date/time, suburb, status, client, lender. Appears after 200ms, disappears on mouse leave. On mobile, long-press (500ms) opens the same preview. Hover does not block click or drag.
- **Booking cards**: Show time, job ref, customer name, booking type. Day view shows full detail, Week view shows compact. Admin sees grab cursor on draggable bookings.
- **Drag-and-drop rescheduling (admin only)**: Admin can drag booking cards to different hour/day cells in Day and Week views. Non-admin users see no drag affordance. After drop, a confirmation overlay shows old/new date/time, job ref, type, and agent — requires explicit Confirm or Cancel. On confirm, posts to `/schedule/api/<id>/reschedule` with `change_method=drag_drop`. On failure, booking snaps back with error message. All drag changes are recorded in booking history with "(drag & drop)" method note.
- **Interaction separation**: hover = preview tooltip, click = action popup, drag = reschedule. Drag threshold prevents accidental moves. Hover hides on drag start. Click suppressed after drag action.
- **Popup detail panel**: Click any booking card to open a rich popup with all booking details (date/time with OVERDUE badge, type, job ref link, job type, customer, address, assigned agent, status, notes). Role-aware action buttons: View Job, Change Booking, History, Complete, Cancel, Copy Ref.
- **Change Booking form**: Inline form in popup to edit date/time, booking type, agent assignment (admin only), and notes. Submits via AJAX to `POST /schedule/api/<id>/update` with minute-level datetime precision comparison, booking type validation, and granular change history tracking. Supports unassign (empty agent).
- **Booking History panel**: Shows full audit trail fetched from `GET /schedule/api/<id>/history` with colour-coded action labels (created/rescheduled/completed/cancelled/updated), timestamps, notes, and changed-by user.
- **Quick actions**: Complete and Cancel with confirmation prompts via `POST /schedule/api/<id>/complete` and `POST /schedule/api/<id>/cancel`.
- **API**: `GET /schedule/api/events?start=&end=&agent_id=&status_filter=` returns JSON events (including `booking_type_id`, `client_name`, `lender_name`) for the requested range. Lazy-loaded by visible date range only.
- **Booking history**: `schedule_history` table tracks all mutations (created, rescheduled, cancelled, completed, updated) with old/new state, changed_by, and notes. Preserves original schedule entries even after changes.
- **Quick action endpoints**: `POST /schedule/api/<id>/reschedule`, `POST /schedule/api/<id>/complete`, `POST /schedule/api/<id>/cancel`, `POST /schedule/api/<id>/update`, `GET /schedule/api/<id>/history`.

**3. Cues System:** Manages `cue_items` (scheduled tasks) with properties like date, visit type, priority, and agent assignment. Supports daily cue access for agents and drag-and-drop assignment for admins, with automatic cue generation for overdue or upcoming schedules.

**4. Audit Log:** Logs all significant system actions, accessible via the admin dashboard.

**5. Field Resources Management:** Centralized management of Tow Operators and Auction Yards with interactive modals for adding, editing, and deleting entries.

**6. Forms Module:** Grid-based dashboard for 7 active form types (SWPI VIR, Transport Instructions, Voluntary Surrender, Form 13, Wise VIR, Auction Letter, Tow Letter). Forms are editable HTML with pre-populated fields saving to DB before PDF generation via ReportLab. Signatures captured live via canvas pads — NOT stored in DB. After every PDF is generated, it is auto-saved to job_documents and a note added to job_field_notes. Filename format: "[JobNumber] - [Form Name] - [DD-MM-YYYY].pdf". Complete Repo Pack (GET) merges unsigned reference copies and also attaches to the job.

**7. Job Creation Enhancements:** Improved job creation flow with client job number tracking, reference search, and a "Clone" functionality for pre-filling new job forms.

**8. CSV Job Import:** Bulk import of job data via CSV files, with duplicate handling. Accessed from Settings & Resources → Import & Data tab (no longer in the main nav). Form posts to `POST /import/jobs`, redirects back to settings after completion. `GET /import/jobs` redirects to `/admin/settings#import-data`.

**8a. Import & Data Management (Settings):** The "Import & Data" tab in Settings groups all data management tools:
- **Import Jobs**: CSV upload form (inline within settings)
- **GeoOp Import Pipeline**: Link to dedicated `/admin/geoop-import` page
- **Duplicate Finder**: Quick link to the Duplicate Finder tab
- **Future placeholders**: Data Repair Tools, Bulk Client Linking, System Data Cleanup (structured but not yet implemented)

**8c. GeoOp Staged Import Pipeline (`/admin/geoop-import`):**
- **Password-gated access**: All GeoOp import routes use `@geoop_required` decorator — requires admin login PLUS a separate GeoOp password (stored in `GEOOP_PASSWORD` env secret). Unlock is per-session and user-bound (`session['geoop_unlocked']` = user ID). If `GEOOP_PASSWORD` is not set, the entire section is disabled. Login page at `/admin/geoop-login`. Uses `hmac.compare_digest` for constant-time comparison.
- 3-step pipeline: Stage CSV → Review Diagnostics → Execute Import
- Uses `geoop_import.py` module with 4 staging tables (`geoop_staging_jobs`, `geoop_staging_notes`, `geoop_staging_files`, `geoop_import_runs`)
- `parse_description()` extracts from free-text GeoOp Description field: client name, account number, regulation type, amounts, costs, NMPD, security vehicle details (colour/year/make/model/REG/VIN), and deliver_to
- Stage: Upload jobs.csv and notes.csv, parsed into staging tables with description field extraction
- Diagnostics: JSON API showing parse coverage percentages, status breakdown, sample parsed jobs, unparsed samples
- Import: Insert-only or update mode; creates jobs, customers, security items, phone numbers, schedules, and optionally notes
- Import history table tracks all stage/import runs with stats
- Reset button clears all staging data
- **Attachment workflow**: CSV staging creates manifest references (`source_type='note_csv'`/`'job_csv'`), not physical files. Physical files are scanned separately via "Scan Attachments" against an extracted attachment folder (`source_type='disk_scan'`, `found_on_disk=1`).
- **Attachment reconciliation** (in diagnostics panel): Shows manifest records total, physical files scanned total, matched manifest↔physical, missing physical files, unmatched physical files (no CSV reference), and duplicates by hash. Reconciliation section only shows detailed breakdown after a disk scan has been performed.
- **Azure Blob Storage attachment import**: Accepts a container SAS URL (`POST /admin/geoop-import/scan-azure`), streams blobs matching `attachments/{job_id}/{note_id}/{file_id}_{filename}` **or** `{account_id}/{job_id}/{note_id}/{filename}` path formats (both supported via `_parse_attachment_path()` fallback), matches against imported staging notes by GeoOp Job/Note ID, and links files to Axion notes via `job_note_files`. Zip archives are streamed via `download_blob().chunks()` and extracted automatically. MD5 deduplication prevents duplicate imports. Files are stored via the app's `_save_bytes_to_storage` function (Azure Blob or local fallback). SAS URL validated for HTTPS + `*.blob.core.windows.net` + `sig=` parameter. Errors are logged server-side only (no SAS token exposure in flash messages). Source type tracked as `azure_blob` in `geoop_staging_files`. Run type `azure_blob_scan` in `geoop_import_runs`. **Runs as a background thread** — the HTTP request returns immediately with a flash message, and the UI polls `GET /admin/geoop-import/scan-azure/progress/<run_id>` every 3 seconds for live stats (blobs scanned, files processed, linked, duplicates, errors). DB writes use short-lived connections with batched inserts (25 files per batch) and exponential-backoff retry on `sqlite3.OperationalError: database is locked`.
- **Attachment audit & repair**: `GET /admin/geoop-import/attachment-audit` returns cached JSON audit of the entire attachment pipeline (staging counts, linked/unlinked files, file types, pipeline stage status, failed file notes). Audit computation runs on a background thread (`start_attachment_audit_background()`) to avoid blocking the SQLite worker; results cached in `_audit_cache` with thread-safe locking. Use `?action=start` to trigger a fresh audit; poll the same endpoint for results (returns `_audit_status: running|complete|error`). Frontend polls every 2 seconds until complete. `POST /admin/geoop-import/backfill-attachments` re-imports previously skipped/errored notes that have file attachments, creating `job_field_notes` with placeholder text `[Attachment: {filename}]` for attachment-only notes. Runs as background thread with progress polling via `GET /admin/geoop-import/attachment-backfill-progress/<run_id>`. Admin UI: "Attachment Audit & Repair" card with inline audit display and backfill progress panel.
- **Note import fix**: `import_staged_notes()` no longer skips notes with empty text if they have a `file_name` — prevents orphaning of 369 attachment-only notes. Empty-text file notes get placeholder text `[Attachment: {filename}]`. Multi-file children (file-only notes sharing a parent's `files_location` but with different `geoop_note_id`) are marked `linked_to_parent` instead of creating redundant Axion notes — the Azure scanner links their files to the parent note via `job_note_files`. A reconciliation pass after the main import loop resolves any `linked_to_parent` rows where the parent wasn't imported yet.
- **Audio/media playback**: Notes with M4A, WAV, MP3, OGG, AAC audio files get inline HTML5 audio playback in both desktop and mobile preview modals. Extended image format support: AVIF and JFIF display as thumbnails and inline previews. Audio files show an amber M4A icon in the thumbnail grid.
- **SQLite concurrency**: All connections (`db()` in app.py, `_db()` in geoop_import.py) use WAL journal mode, `synchronous=NORMAL`, `busy_timeout=60000`, and `timeout=30`. Schema init (`init_db()` + `_migrate_update_builder()`) runs once per process via `_db_initialized` flag, not on every request — prevents write contention during long-running imports.
- **Top-level stat cards**: "Manifest References" (CSV export refs, purple) + "Physical Files Scanned" (disk, green/grey) + "Azure Attachments Linked" (blob storage, cyan/grey). Old "File Records" label replaced to avoid implying files are uploaded.
- **Attachment file linking**: `_link_staged_attachments()` sweeps all staging notes with resolved `axion_note_id` + `file_name` and inserts missing `job_note_files` rows. Uses `INSERT OR IGNORE` against unique index `idx_jnf_note_file(job_field_note_id, filename)` for idempotency. Preloads `geoop_staging_files` stored_filename map into memory to avoid N+1 queries. `_ensure_job_note_file()` called inline during both `import_staged_notes()` and `backfill_attachment_links()`. `_resolve_stored_name()` resolves UUID stored names from `geoop_staging_files` with deterministic `ORDER BY id DESC`.
- **Date repair**: `POST /admin/geoop-import/repair-dates?target=notes|jobs|both` retroactively fixes `created_at`/`updated_at` on already-imported jobs and notes by cross-referencing `geoop_staging_jobs.date_created`/`date_modified` and `geoop_staging_notes.file_date`. Both `import_staged_notes()` and `backfill_attachment_links()` now use `job_date_map` preloaded from staging data to set correct original dates during import (file_date for attachment notes, job's date_modified as fallback for text-only notes).
- **Phone number repair**: `_preserve_phone_text()` restores leading zeroes (9-digit → prepend `0`) and `+61` international prefixes (11-digit starting with `61` → prepend `+`) stripped by Excel/CSV numeric coercion. Applied during CSV staging, during import to `contact_phone_numbers`, and available as retroactive repair via `POST /admin/geoop-import/repair-phones`. Repair scans both `contact_phone_numbers` and `geoop_staging_jobs` phone/mobile fields.
- **Data Repair Tools UI**: "Repair Original Dates" and "Repair Phone Numbers" buttons in the Attachment Audit & Repair card on the GeoOp import page, with unified progress polling via `GET /admin/geoop-import/repair-progress` showing live status for notes, jobs, and phones.
- **GeoOp Job ID mapping (`geoop_job_id` column)**: The `jobs` table has a nullable TEXT `geoop_job_id` column storing the original GeoOp internal job ID. Populated during `import_staged_jobs()` for new and updated jobs. Used by `recover_files_from_zips()` for direct attachment linking when staging file mappings are missing. ZIP paths `attachments/{account_id}/{geoop_job_id}/{note_id}/{filename}` are parsed by `_parse_zip_entry_path()` which correctly handles both 5-part (with account_id prefix) and 4-part (without) formats. `backfill_geoop_job_ids()` populates the column for previously imported jobs from `geoop_staging_jobs` data (safe mode: only updates NULL/blank values, logs conflicts). Admin button "Backfill GeoOp Job IDs" on the GeoOp Import page (`POST /admin/geoop-import/backfill-job-ids`). Recovery flow: run backfill first, then ZIP file recovery — files without staging mappings are matched directly by `geoop_job_id` on the jobs table and linked via `job_note_files`.
- **Phone click actions**: All phone numbers across the platform support tap-to-call, SMS, and WhatsApp via `axPhone()` action sheet (desktop + mobile). `axLinkPhones()` auto-detects and links phone numbers in free text (note content).
- **File recovery from ZIPs**: `POST /admin/geoop-import/recover-files` extracts physical attachment files from GeoOp ZIP archives into the uploads directory, using existing `geoop_staging_files.stored_filename` database mappings. Idempotent (skips files already on disk). Background thread with progress polling via `GET /admin/geoop-import/recover-files-progress`. ZIP directory defaults to `uploads/geoop_import`. Parses ZIP entry paths using same `attachments/{job_id}/{note_id}/{file_id}_{filename}` format as Azure blob scanner.
- Routes: `GET /admin/geoop-import`, `POST /admin/geoop-import/stage`, `GET /admin/geoop-import/diagnostics`, `POST /admin/geoop-import/execute`, `POST /admin/geoop-import/reset`, `POST /admin/geoop-import/scan-attachments`, `POST /admin/geoop-import/scan-azure`, `GET /admin/geoop-import/attachment-audit`, `POST /admin/geoop-import/backfill-attachments`, `GET /admin/geoop-import/attachment-backfill-progress/<run_id>`, `POST /admin/geoop-import/link-staged-attachments`, `POST /admin/geoop-import/repair-dates`, `GET /admin/geoop-import/repair-dates-progress`, `POST /admin/geoop-import/repair-phones`, `GET /admin/geoop-import/repair-progress`, `POST /admin/geoop-import/recover-files`, `GET /admin/geoop-import/recover-files-progress`
- Template: `templates/geoop_import.html`

**8d. File Lifecycle System (Archive & Cold Storage):**
- **Three-tier lifecycle**: Active → Archived – Invoiced → Cold Storage. Files progress through tiers based on operational status and age.
- **Statuses**: `Archived - Invoiced` (removed from active views, fully searchable), `Cold Stored` (metadata searchable, attachments in compressed storage).
- **Database**: `lifecycle_status` column on `jobs` (`active`, `archived`, `cold_stored`, `retrieval_pending`, `retrieved`). `job_lifecycle_log` audit table tracks all lifecycle transitions. `archived_at`, `archived_by_user_id`, `cold_stored_at`, `cold_stored_by_user_id`, `cold_storage_ref` on `jobs`.
- **Active view exclusion**: Archived/Cold Stored jobs automatically excluded from: Jobs list (unless status filter explicitly set), Queue, Schedule, Mobile jobs, LPR watchlist, Dashboard counts. `ARCHIVED_STATUSES` constant defined at module level.
- **Archive actions**: `POST /jobs/<id>/archive` (single), `POST /jobs/<id>/restore` (restore to Invoiced/Completed/Active), `POST /admin/archive/bulk` (bulk archive with batch_id tracking), `POST /admin/archive/bulk-all` (archive ALL eligible jobs matching current filters, JSON-only with CSRF check, batch commits every 500).
- **Archive search**: `GET /admin/archive` with two modes: "Search Archive" (search by ref, customer, reg, VIN, address, client, date range) and "Archive Eligible Files" (find Invoiced/Completed older than X days for bulk archiving). Eligible query includes GeoOp-imported jobs (`geoop_source_description IS NOT NULL`) regardless of date filter since import set `created_at`/`updated_at` to transfer date not original dates. Results paginated at 500 per page with total count display and "Archive All" button for full-batch operations.
- **Job detail banners**: Archived jobs show amber "Archived Historical File" banner with restore options. Cold Stored jobs show purple "Cold Storage File" banner with retrieval request.
- **Settings**: Data Management tab in Settings with archive policy configuration (archive_after_days, cold_store_after_years, archive/cold_storage mode, allow_restore, allow_permanent_delete). Route: `POST /admin/settings/archive`.
- **Dashboard**: Streamlined layout with 4 large clickable summary cards (Total Active, Needs Attention, Awaiting Response, Completed) at top. Clicking a card loads up to 25 matching jobs via AJAX (`GET /dashboard/jobs?category=`) into a detail panel that replaces Recent Activity. "Back to recent" button restores the default view. Below the cards: compact button-sized status tiles (New, Active, Phone Work, Suspended, Awaiting, Completed Today) with quantity badges linking to filtered job lists. All Jobs, Invoiced, and Archived tiles removed from dashboard. XSS-safe rendering with HTML escaping. Stale request protection via sequence counter.
- **Navigation**: "Archive" link in admin sidebar between Reports and Settings.
- **Audit**: All archive/restore actions logged in `job_lifecycle_log` and `audit_log`. Interactions logged on the job. Bulk operations tracked by batch_id.
- **Phase 2/3 foundation**: Cold storage packaging, attachment compression, Azure Blob cold tier, automated retention processing — schema and settings ready, implementation deferred.
- Routes: `POST /jobs/<id>/archive`, `POST /jobs/<id>/restore`, `POST /admin/archive/bulk`, `GET /admin/archive`, `GET /admin/archive/lifecycle-log/<id>`, `POST /admin/settings/archive`
- Template: `templates/archive.html`

**8b. Duplicate Finder (Settings):** Two-mode duplicate detection tool on the Settings page:
- **Database Scan:** Finds duplicate jobs (by job number or account number) and duplicate clients (by name) already in the system.
- **CSV File Scan:** Multi-file upload (accepts multiple CSVs at once) checks for duplicates within the selected files and against existing database records before import.
- All delete operations use AJAX (`/admin/api/duplicates/delete-job`, `/admin/api/duplicates/delete-client`) so users stay on the Settings page — no redirect to Jobs or Clients lists.
- Summary bar shows file count, total records scanned, and duplicate count after each scan.

**9. AI Update Builder:** Guided form using OpenAI (gpt-4o-mini) to generate SWPI-style attendance updates, featuring auto-filling, fact toggles, AI narrative generation, editable output, and address validation. Two generation modes: (a) **Notes-driven** — when the agent types attendance notes (occupant contact, customer interaction, confirmations, observations), the AI rewrites them into professional SWPI-style prose preserving every fact, with structured field sentences woven in verbatim; (b) **Structured-only** — when no notes are entered, strict deterministic output from form selections only (no AI embellishment). Anti-fabrication rules enforce that the AI never invents events, persons, or interactions not typed or selected. POC closing: "This attendance constitutes N point(s) of contact." Mobile update builder includes site photo attachments (camera + gallery, up to 10 per update, 25 MB each, thumbnail grid with remove) and speech-to-text for attendance notes (Web Speech API, en-AU). Photos are uploaded to `uploads/update_photos/`, tracked in `job_update_photos` table during drafting, and linked to `job_note_files` on save. Photo count is signalled to the AI prompt for context. Desktop update builder has matching photo UI (upload from computer or camera, thumbnail grid with remove, same upload/delete/serve routes).

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
    - **Document Upload / Import Workflow (Web Only):** Extracts data from `.docx`, `.pdf`, `.doc` files for autofilling job creation forms. Named parser profiles for **ACS (Australian Collection Services)** worksheets and **Wise Group** cases. ACS parser: detects by `auscollect.com.au` / worksheet header; maps Client: line as lender, recognises ACS as the referring agency; splits `Regn: X - UNREG` into rego + note; handles combined `Make/Model:` field; extracts rego expiry, financials, delivery destination, and formats instructions into readable sections. Customer regex supports digits in company names (e.g. "INSTALL2U"). Arrears/financial regexes anchored to line start to avoid false matches on instruction text. Guarantor phone fallback: when Mob/PhHm/PhBus are all empty, extracts standalone phone number from the G/tor section. Generic parser fallback includes combined `Make/Model:` field support and `VIN #:` format. `.doc` files: tries antiword first, falls back to olefile OLE2 stream parsing. Security form includes **colour** field with auto-sync to description. Confidence badges: Matched (green), Created/New (purple), Extracted (blue), Review (amber). `_source` label shown in autofill banner (e.g. "ACS Worksheet"). **Auto-create customer**: When no existing customer matches the extracted name, a new customer record is automatically created from extracted data (name, address, DOB, phone, email) with phone/email saved to `contact_phone_numbers`/`contact_emails`. Badge shows "New" (purple) for auto-created customers vs "Matched" (green) for existing. Error-safe with try/except and logging.
    - **Camera Stability (Native + Web):** `LiveLPRScannerView` checks `AVCaptureDevice.authorizationStatus` before session setup; handles `.notDetermined` (requests permission), `.denied` (shows "Camera Access Blocked" with Open Settings), `.restricted` (shows restriction message), and setup failures (shows error detail). Error overlay offers Retry / Manual Plate Entry / Cancel so agents are never blocked. Web `lpr_capture.html` validates file size (25 MB max), file type, and empty submissions client-side. Server `/m/lpr/capture` wraps `extract_plate_from_image()` in try/except so corrupted images return empty plate for manual correction instead of crashing. `LPRCameraViewController` uses `beginConfiguration/commitConfiguration` pattern, `[weak self]` in all async paths, and explicit do/catch around Vision requests and torch configuration.
    - **Floating LPR FAB (Multi-step inline sheet):** Persistent FAB on all mobile screens opens a 3-step sheet: (1) action chooser with Patrol Mode featured + Live Scan / Take Photo / Manual Entry / Patrol Intel grid, (2) inline plate entry with JSON lookup, (3) full result display with Save Sighting — no navigation away from current screen. `window.handleNativePlateScan` defined globally for iOS bridge.
    - **Patrol Mode (`/m/lpr/patrol-mode`):** Full-screen live camera continuous scanning mode. Captures frames every 2.5s via `getUserMedia`+canvas, POSTs to `POST /m/api/lpr/patrol-scan` (Tesseract OCR → allocation lookup), 30s client-side duplicate suppression per plate. Shows status overlay, viewfinder, live plate feed, torch control. On allocated/restricted/watchlist match: high-visibility alert with haptic feedback, Open Job / Contact Office / Save Sighting (with GPS) / Continue Scanning. Manual plate entry within patrol mode. Stop Patrol returns to jobs. Feature flag: `system_settings.lpr_patrol_mode_enabled` (default 1). **Camera error differentiation**: distinct messages for build missing camera support, permission denied, no camera hardware, camera init failure, insecure context, and overconstrained settings (auto-fallback to basic config). **Diagnostics panel**: hidden panel (tap scan count 5 times to reveal) showing platform, native wrapper status, bridge availability, secure context, mediaDevices/getUserMedia support, camera state, permission status, scanner active, torch support, scan count, and user agent — for rapid field troubleshooting.

**13. Quick Field Notes (Mobile):** Rich note-taking from job detail screen. Backend: `note_type` + `audio_filename` columns on `job_field_notes`; `POST /m/job/<id>/quick-note` (multipart text/audio/photo); `GET /m/note-audio/<note_id>`, `GET /m/note-photo/<file_id>` serving routes. Notes tab: type icon pills, photo thumbnails with lightbox, inline audio players, agent/timestamp. Add Note bottom sheet: text, MediaRecorder voice (pulsing indicator, 3-min limit), camera/gallery photo; live-injects new note card without page reload.

**13a. Notes Editing & Multi-Document Upload (Desktop):**
- **Click-to-edit**: Entire note row is clickable — opens the Edit Note modal. Hover shows subtle highlight and pointer cursor. Action buttons (checkbox, delete, download, email) inside the row are excluded from the click via event delegation.
- **Edit Note modal** (`#editNoteModal`): Full edit screen with note text editor, metadata display (created by, date/time, last updated by/at), admin-only staff/datetime override, current attachments list (with type icon, filename, upload date, download link, remove button), and drag-and-drop file upload zone.
- **Multi-file upload to existing notes**: "Add Files" input and drag-and-drop zone accept multiple PDF/DOC/DOCX/image files in one action. Files append to existing attachments without replacing them. Upload status indicator shown during upload.
- **Attachment management**: View, download, and remove individual attachments. Remove confirms before deleting. File count badge shown.
- **Audit trail**: `updated_at` and `updated_by_user_id` columns on `job_field_notes` track last edit. Attachment additions/removals logged via audit system.
- **API routes**: `GET /jobs/<id>/notes/<nid>/detail` (note metadata + files), `POST /jobs/<id>/notes/<nid>/attachments` (multi-file upload), `POST /jobs/<id>/notes/<nid>/attachments/<fid>/delete` (remove single file). Edit route (`POST /jobs/<id>/notes/<nid>/edit`) also supports file uploads alongside text edits.
- **File storage**: `upload_to_blob()` now falls back to local `uploads/` folder when Azure Blob Storage is not configured.

**12. Repo Lock (v2):** Per-security-item repossession record accessible on desktop and mobile. Features draft saving and submission workflows, generating formatted notes and linking to PDF generation for VIR, Transport Instructions, and other forms. Includes signature capture and PDF generation via `pdf_gen.py`.

**17. Unified Authentication Routing:**
- `_is_mobile_request()` detects mobile context via path prefix (`/m/`), native app UA (`AxionX/`), or iOS/Android device UAs (iPhone, iPad, iPod, Android).
- `_login_redirect()` routes unauthenticated users to `/m/login` (mobile) or `/login` (web) based on device detection.
- `login_required` and `admin_required` decorators both use `_login_redirect()`.
- `/login` GET redirects mobile UAs to `/m/login` — ensures all auth states (session expiry, logout, failed login) converge on the same mobile login template.
- `/logout` detects mobile and redirects to `/m/login` instead of `/login`.
- `/` root route detects mobile and redirects authenticated users to `/m/schedule/today`, unauthenticated to `/m/login`.
- Inline auth checks in `/my/settings` and `/jobs/<id>/note-update-emailed` use `_login_redirect()`.
- Web login CSS: login card vertically centered on mobile screens (<860px) via flexbox `justify-content:center` and `min-height:100dvh`.

**14. Biometric Login (Face ID / Touch ID):**
- **Backend**: `mobile_auth_tokens` table (token, user_id, device_name, created_at, expires_at, revoked_at). API: `POST /m/api/auth/create-token` (90-day token), `POST /m/api/auth/token-login` (validates token, creates fresh Flask session), `POST /m/api/auth/revoke-token`, `GET /m/api/auth/biometric-status`, `POST /m/api/auth/revoke-all-tokens`. Logout (`GET /m/logout`) accepts optional `?token=` param for server-side revocation.
- **iOS Native**: `BiometricAuthService` stores auth token (not session cookie) in Keychain via `KeychainService.saveToken/loadToken`. On biometric auth success, calls `/m/api/auth/token-login` to get fresh session cookies injected into WKWebView. `LoginView` shows opt-in alert after first successful login ("Enable Face ID/Touch ID?"). UserDefaults: `biometric_opted_in`, `biometric_declined`. `ContentView` auth flow: check Keychain token → biometric prompt → token-login → WebView.
- **Single Login Screen Architecture**: All auth exits (logout, session expiry, failed login, app relaunch) return to the native SwiftUI `LoginView` — never the web login page. `WebViewNavigationDelegate` intercepts any navigation to `/m/login` or `/login` before the page loads, posts `.axionSessionExpired` notification, and cancels navigation. `ContentView` observes this notification and transitions to `.unauthenticated` state. `LoginView` uses `GeometryReader` with solid color fallback behind `AppBackground` image for guaranteed full-screen coverage on all iPhone sizes.
- **Settings Bridge**: `BiometricSettingsHandler` (WKScriptMessageHandler) registered as `biometricSettings` messageHandler. Actions: `getStatus`, `enable`, `disable`, `resetDecline`, `resetSession`. Web settings page communicates via `window._biometricCallback` pattern.
- **Mobile Settings**: Biometric Login card in `/m/settings` (native wrapper only). Shows biometric type, enable/disable toggle, Reset Saved Login button. Hidden when not in iOS wrapper.
- **Info.plist**: `NSFaceIDUsageDescription` present, `NSMicrophoneUsageDescription` present (required for voice notes in Add Note).

**15. Internal Messaging System:** Staff messaging (admin↔agent, agent↔agent) with job-linked and direct conversations.
- Tables: `conversations` (type: direct|job, optional job_id), `conversation_participants`, `messages`, `message_reads`
- Desktop: Two-panel layout at `/messages` and `/messages/<conv_id>`. Left sidebar = conversation list; right = chat bubbles. Reply with Enter key or Send button.
- Mobile: Full-screen conversation list at `/m/messages`; chat interface at `/m/messages/<conv_id>` with pinned reply bar.
- New message modal (desktop) + compose sheet (mobile): multi-recipient checkboxes with "Broadcast to All" toggle, optional job link, first message body. Broadcast sends the same message as separate conversations to each selected recipient. Single recipient opens the conversation thread directly; multi-recipient redirects to the messages list with a confirmation flash.
- Unread badge: blue count badge in desktop sidebar nav + dot indicator on mobile "Msgs" tab. Both poll `/api/messages/unread-count` every 30s (mobile 15s). Desktop shows a toast notification when new messages arrive. Mobile shows a slide-down toast banner that navigates to `/m/messages` when tapped.
- Push notifications: `_post_message()` sends APNs push to all conversation recipients (sender's `full_name` as title, message preview as body). Payload includes `{type: "message", conv_id: <id>}`. iOS app routes message notifications to `/m/messages/<conv_id>` and LPR notifications (type "lpr") to `/m/lpr/notifications`.
- Job-linked conversations show a yellow banner with clickable link to the job.
- Shared API: `GET /api/messages/unread-count`, `POST /messages/<conv_id>/read`

**16. Customer & Client List Search:**
- Both `/customers` and `/clients` pages include a search field at the top of the list.
- **Customer search** queries: first_name, last_name, full name (both orders), company, email, address, phone numbers (via contact_phone_numbers), emails (via contact_emails), and linked job references (client_reference, account_number).
- **Client search** queries: name, nickname, phone, email, address, notes, and linked phone numbers/emails from contact tables.
- All searches: partial match, case-insensitive, trimmed input, debounced 300ms search-as-you-type.
- Server-backed via `X-Requested-With: search` header returning JSON — searches full dataset, not just visible rows.
- Search persistence: `sessionStorage` saves the active query so navigating to a record and coming back restores the search.
- Clear button (×) and Escape key reset search and restore full list.
- Empty results show "No customers or contacts found" / "No clients found".
- Result count shown below search field.
- Consistent UI between both lists: identical field placement, placeholder style, clear button, status line.

**15. Customer Call/SMS Actions:**
- `customer_detail.html`: Phone numbers show inline Call (green) + SMS (blue) buttons with `tel:` and `sms:` schemes.
- `job_detail.html`: Linked customer rows show primary phone with Call + SMS buttons. Client phone shows Call button.
- Mobile: Already had Call/SMS on job detail; now consistent across all platforms.

## Infrastructure & Deployment

- **Database**: SQLite. Both `app.py` and `geoop_import.py` resolve to the same absolute path via `os.path.abspath(os.getenv("DB_PATH", "axion.db"))`. On Azure, `startup.sh` exports `DB_PATH=/home/site/data/axion.db` (persistent mounted storage) before launching gunicorn, since Oryx extracts the app to a temporary `/tmp/` path. On Replit, defaults to `./axion.db`. All connections use WAL mode, `synchronous=NORMAL`, and `busy_timeout=60000`.
- **Schema init**: `init_db()` and `_migrate_update_builder()` run lazily on first `db()` call via `_lazy_init()` with thread-safe double-check locking. Not at module import time (avoids crash if DB is unavailable during worker boot) and not in `@app.before_request` (avoids per-request overhead). `now_ts()` is defined before `init_db()` to avoid NameError on fresh databases.
- **Gunicorn**: Single worker (`--workers 1`) in both Replit (port 5000) and Azure deployment (`startup.sh`, port 8000). Required while SQLite is the database engine.
- **Azure Blob scan progress**: Persisted to `geoop_import_runs.diagnostics_json` column via `_persist_scan_progress()`. No in-memory state — safe across app restarts and worker recycles. Progress updated every 200 ZIP entries and at each phase transition.
- **Azure Blob listing**: Uses `list_blobs(name_starts_with=blob_prefix)` with default prefix `None` (scan all). Root-level ZIP archives are streamed via `_AzureBlobFile` (seekable wrapper using Azure range requests with 4MB buffering) — no temp file download required.
- **PMT Due Date auto-advance**: `advance_due_date_display()` in `app.py` advances past due dates to the next upcoming date using `payment_frequency`. Defaults to monthly if no frequency is set, so GeoOp-imported NMPD dates always auto-advance. GeoOp import now sets `payment_frequency='Monthly'` when importing NMPD dates (INSERT, UPDATE, backfill, and repair paths all updated). The display function handles fortnightly/weekly/monthly cycles with a max 1000 iteration guard.
- **GeoOp Description preservation**: Raw GeoOp description text is stored in `jobs.geoop_source_description` (immutable) AND as a `job_field_notes` record with `note_type='geoop_import'`. Structured fields (reg, VIN, arrears, costs, NMPD/next payment, regulation type, security details) are parsed via `parse_description()` and populated on both `jobs` and `job_items`. `backfill_geoop_descriptions()` runs as a background job with batched processing (250 per batch), progress checkpointing, singleton guard, and safe resume (CASE WHEN blank-only semantics, idempotent). Progress is polled via `/admin/geoop-import/backfill-progress/<run_id>`.
- **GeoOp Client import**: `parse_description()` extracts `parsed_client_name` from GeoOp job descriptions (~39% of 15,587 jobs have parseable client names; remaining 60% start with "Regulated/Unregulated" with no client info in the description). Parser handles: dual-account slash ("Name ID / Name2 ID2"), dash-ID ("Name - ID Regulated"), name-before-regulation-type, field-call, on-behalf-of, colon-prefix, hash-prefix, and mid-string search patterns. Prefix stripping handles "REPOSSESSION AUTHORITY...COMMENCES" and "** instruction **" blocks. `_match_client(conn, name)` matches parsed names to the `clients` table via exact, normalised (strips Pty Ltd/Finance/Leasing suffixes), primary-word-overlap, and prefix matching. `import_staged_jobs()` sets `client_id` on INSERT/UPDATE using fallback order: parsed_client_name → Company field. `backfill_client_links(run_id)` re-parses and matches all imported jobs missing `client_id` as a background task with progress tracking. `get_client_gap_report()` returns JSON/CSV diagnostic of all unmatched jobs with failure reasons (no_source_data, parse_failed, no_client_match). Admin UI: Client Backfill button + progress panel + Client Gap Report CSV/JSON download links at `/admin/geoop-import`.
- **Scan/Backfill sample verification**: Admin UI displays 10 sample unmatched entries and 5 sample matched attachments after an Azure scan completes, plus 5 sample backfilled jobs with GeoOp Description → structured field mapping after a backfill completes. All samples are run-scoped via `scan_ts`/`backfill_ts` stored in `diagnostics_json`. Unmatched CSV download available via `/admin/geoop-import/unmatched-report/<run_id>/csv`.
- **Unmatched attachment tracking**: `geoop_unmatched_attachments` table stores every unmatched ZIP entry with `run_id`, `zip_name`, `entry_path`, `reason`. Flushed in batches during scan. `get_unmatched_report()` aggregates by reason.

## External Dependencies

- **Database**: SQLite
- **Frontend Libraries**: Bootstrap 5.3.3, Google Maps API, Leaflet.js, Leaflet.markercluster
- **Backend Libraries**: Flask, `python-docx`, `pypdf`, `httpx[http2]`, `PyJWT`, `olefile`, `antiword` (external binary, optional — `olefile` provides Python-native `.doc` fallback when antiword is unavailable, e.g. Azure deployment)
- **AI Services**: OpenAI (gpt-4o-mini), Apple Core ML
- **Mobile-Specific (iOS)**: WKWebView, SwiftUI, CoreLocation, NWPathMonitor, UNUserNotificationCenter, BackgroundTasks, MapKit