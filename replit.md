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

**2c. Job List (Mobile — Distance Default + Search):**
- Mobile app defaults to **Distance – Nearest First** sorting when GPS is available.
- If GPS permission is denied, falls back to Visit Date sort with a warning banner.
- Distance calculated client-side using Haversine formula with server-assisted batch geocoding for missing coordinates.
- **Search**: Search icon positioned right-aligned in input. Client-side filter checks ref (display_ref, internal_job_number, client_reference, account_number), customer, address, reg, vin, lender. When query ≥ 2 chars, a debounced server-side search (`GET /m/api/jobs/search?q=`) fetches additional results beyond the 300-job client-side cap, appended below a "additional results from full search" banner. Server search covers all reference fields plus client_job_number. When a search query (`q`) is active, scope/completed/status filters are bypassed so matching jobs are always found.

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
- **Duplicate Finder**: Quick link to the Duplicate Finder tab
- **Future placeholders**: Data Repair Tools, Bulk Client Linking, System Data Cleanup, Import History (structured but not yet implemented)

**8b. Duplicate Finder (Settings):** Two-mode duplicate detection tool on the Settings page:
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
    - **Document Upload / Import Workflow (Web Only):** Extracts data from `.docx`, `.pdf`, `.doc` files for autofilling job creation forms. Named parser profiles for **ACS (Australian Collection Services)** worksheets and **Wise Group** cases. ACS parser: detects by `auscollect.com.au` / worksheet header; maps Client: line as lender, recognises ACS as the referring agency; splits `Regn: X - UNREG` into rego + note; handles combined `Make/Model:` field; extracts rego expiry, financials, delivery destination, and formats instructions into readable sections. Generic parser fallback includes combined `Make/Model:` field support and `VIN #:` format. Security form includes **colour** field with auto-sync to description. Confidence badges: Matched (green), Extracted (blue), Review (amber). `_source` label shown in autofill banner (e.g. "ACS Worksheet").
    - **Camera Stability (Native + Web):** `LiveLPRScannerView` checks `AVCaptureDevice.authorizationStatus` before session setup; handles `.notDetermined` (requests permission), `.denied` (shows "Camera Access Blocked" with Open Settings), `.restricted` (shows restriction message), and setup failures (shows error detail). Error overlay offers Retry / Manual Plate Entry / Cancel so agents are never blocked. Web `lpr_capture.html` validates file size (25 MB max), file type, and empty submissions client-side. Server `/m/lpr/capture` wraps `extract_plate_from_image()` in try/except so corrupted images return empty plate for manual correction instead of crashing. `LPRCameraViewController` uses `beginConfiguration/commitConfiguration` pattern, `[weak self]` in all async paths, and explicit do/catch around Vision requests and torch configuration.
    - **Floating LPR FAB (Multi-step inline sheet):** Persistent FAB on all mobile screens opens a 3-step sheet: (1) action chooser with Patrol Mode featured + Live Scan / Take Photo / Manual Entry / Patrol Intel grid, (2) inline plate entry with JSON lookup, (3) full result display with Save Sighting — no navigation away from current screen. `window.handleNativePlateScan` defined globally for iOS bridge.
    - **Patrol Mode (`/m/lpr/patrol-mode`):** Full-screen live camera continuous scanning mode. Captures frames every 2.5s via `getUserMedia`+canvas, POSTs to `POST /m/api/lpr/patrol-scan` (Tesseract OCR → allocation lookup), 30s client-side duplicate suppression per plate. Shows status overlay, viewfinder, live plate feed, torch control. On allocated/restricted/watchlist match: high-visibility alert with haptic feedback, Open Job / Contact Office / Save Sighting (with GPS) / Continue Scanning. Manual plate entry within patrol mode. Stop Patrol returns to jobs. Feature flag: `system_settings.lpr_patrol_mode_enabled` (default 1). **Camera error differentiation**: distinct messages for build missing camera support, permission denied, no camera hardware, camera init failure, insecure context, and overconstrained settings (auto-fallback to basic config). **Diagnostics panel**: hidden panel (tap scan count 5 times to reveal) showing platform, native wrapper status, bridge availability, secure context, mediaDevices/getUserMedia support, camera state, permission status, scanner active, torch support, scan count, and user agent — for rapid field troubleshooting.

**13. Quick Field Notes (Mobile):** Rich note-taking from job detail screen. Backend: `note_type` + `audio_filename` columns on `job_field_notes`; `POST /m/job/<id>/quick-note` (multipart text/audio/photo); `GET /m/note-audio/<note_id>`, `GET /m/note-photo/<file_id>` serving routes. Notes tab: type icon pills, photo thumbnails with lightbox, inline audio players, agent/timestamp. Add Note bottom sheet: text, MediaRecorder voice (pulsing indicator, 3-min limit), camera/gallery photo; live-injects new note card without page reload.

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
- **Settings Bridge**: `BiometricSettingsHandler` (WKScriptMessageHandler) registered as `biometricSettings` messageHandler. Actions: `getStatus`, `enable`, `disable`, `resetDecline`, `resetSession`. Web settings page communicates via `window._biometricCallback` pattern.
- **Mobile Settings**: Biometric Login card in `/m/settings` (native wrapper only). Shows biometric type, enable/disable toggle, Reset Saved Login button. Hidden when not in iOS wrapper.
- **Info.plist**: `NSFaceIDUsageDescription` present, `NSMicrophoneUsageDescription` present (required for voice notes in Add Note).

**15. Internal Messaging System:** Staff messaging (admin↔agent, agent↔agent) with job-linked and direct conversations.
- Tables: `conversations` (type: direct|job, optional job_id), `conversation_participants`, `messages`, `message_reads`
- Desktop: Two-panel layout at `/messages` and `/messages/<conv_id>`. Left sidebar = conversation list; right = chat bubbles. Reply with Enter key or Send button.
- Mobile: Full-screen conversation list at `/m/messages`; chat interface at `/m/messages/<conv_id>` with pinned reply bar.
- New message modal (desktop) + compose sheet (mobile): select recipient, optional job link, first message body.
- Unread badge: blue count badge in desktop sidebar nav + dot indicator on mobile "Msgs" tab. Both poll `/api/messages/unread-count` every 30 seconds. Desktop shows a toast notification when new messages arrive.
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

## External Dependencies

- **Database**: SQLite
- **Frontend Libraries**: Bootstrap 5.3.3, Google Maps API, Leaflet.js, Leaflet.markercluster
- **Backend Libraries**: Flask, `python-docx`, `pypdf`, `httpx[http2]`, `PyJWT`, `antiword` (external binary)
- **AI Services**: OpenAI (gpt-4o-mini), Apple Core ML
- **Mobile-Specific (iOS)**: WKWebView, SwiftUI, CoreLocation, NWPathMonitor, UNUserNotificationCenter, BackgroundTasks, MapKit