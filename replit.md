# Axion Prototype

## Overview
Axion Prototype is a Flask-based field operations management application designed for efficient tracking of jobs, clients, customers, assets, cues, and staff. The system aims to streamline field operations, improve job dispatching, and enhance agent productivity through intelligent automation and mobile integration. Key capabilities include comprehensive job management, role-based access, a dynamic queueing system for tasks, audit logging, monthly reporting, and robust field resource management. The project is focused on delivering a robust, scalable solution for field operations, with a strong emphasis on mobile accessibility and data-driven decision-making.

A core component of Axion is the Licence Plate Recognition (LPR) system, which includes advanced features for real-time plate lookups, watchlist hits, agent dispatch, and predictive patrol intelligence. This system leverages AI/ML to identify high-opportunity patrol areas, refine predictions, and automate aspects of the dispatch process.

## User Preferences
No explicit user preferences were provided in the original `replit.md` file. The document primarily describes system features and technical implementation details.

## System Architecture

### Core Technologies
- **Backend**: Python 3.11 with Flask 3.0.3
- **Database**: SQLite (`axion.db`)
- **Frontend**: Jinja2 templates, Bootstrap 5.3.3 (CDN) for styling, and custom JavaScript for interactivity.
- **Mobile Wrapper**: Native iOS application (SwiftUI, WKWebView) for an enhanced mobile experience, wrapping mobile web routes.

### Design Patterns & Features

**1. Role-Based Access Control:**
   - Differentiates between 'Admin' and 'Agent' roles with tailored access to features like job visibility (all vs. own only), dashboards, cues, assignment boards, reports, and user management.

**2. Dynamic Queue System (`/queue`):**
   - Admin-only view presenting 'Overdue', 'Currently Due', and 'Agent Notes — Pending Review' cue items.
   - Supports email composition and job updates directly from the queue.
   - Automatically flags agent notes for review by creating specific `cue_item` entries.

**3. Cues System:**
   - Manages `cue_items` (scheduled tasks) with properties like date, visit type, priority, and agent assignment.
   - Agents access their daily cues via `/my/today`.
   - Admins use `/assign` for drag-and-drop cue assignment.
   - Automatic cue generation for overdue or upcoming schedules.

**4. Audit Log:**
   - Comprehensive logging of all significant system actions, including cue management and user activities, accessible via the admin dashboard.

**5. Field Resources Management (`/resources`):**
   - Centralized management of Tow Operators and Auction Yards, accessible to all logged-in users.
   - Utilizes interactive modals for adding, editing, and deleting entries without full page reloads.

**6. Customizable Job Forms:**
   - "Forms" tab on job detail pages provides pre-defined and custom forms (e.g., Worksheet, VIR).
   - Forms are auto-populated, editable, and print-ready, supporting dynamic dropdowns for field resources.
   - Admin-only form builder for creating custom templates.

**7. Job Creation Enhancements:**
   - Improved job creation flow with client job number tracking and reference search.
   - "Clone" functionality to quickly pre-fill new job forms from existing job data.

**8. CSV Job Import (`/import/jobs`):**
   - Allows admins to upload CSV files to bulk import job data, with duplicate handling.

**9. AI Update Builder (`/jobs/<id>/update-builder`):**
   - Guided form for agents/admins to generate SWPI-style attendance updates using OpenAI (gpt-4o-mini).
   - Features include auto-filling, fact toggles, AI narrative generation, editable output, address validation, and auto-saving with draft management.
   - Incorporates logic for "points of contact" and estimated time of arrival (ETA) calculations.

**10. Geomap & Agent Tracking (`/map`):**
    - Admin-only map view displaying job pins by status and live agent locations.
    - Client-side geocoding for jobs without cached coordinates.
    - Agent GPS tracking (opt-in, silent) with position updates to the backend.

**11. Licence Plate Recognition (LPR) System:**
    - **Offline Queue & Background Sync:** Idempotent backend for sighting saves, ensuring no duplicates on retry. iOS-side `OfflineQueue` and `SyncManager` for robust offline data capture and background synchronization.
    - **Push Notifications & Dispatch:** APNs integration for real-time alerts. Notification triggers for watchlist hits, escalated sightings, proximity alerts, and follow-up assignments. Proximity zone management for admins.
    - **Dispatch Intelligence:** Calculates human-readable distances and ETAs. Identifies nearest agents and repeat plate sightings. Generates dispatch scores and recommended actions based on various factors.
    - **Map Upgrade:** Leaflet.markercluster for enhanced visualization of sightings, with custom cluster icons and filtering options.
    - **Passive Background Location:** iOS `AgentLocationService` with different modes (off-duty, available, active job) for battery-efficient location tracking, capturing battery state and app context. `FieldStatusManager` manages agent availability status.
    - **Route/ETA Intelligence & Native Dispatch:** Integrates `DispatchManager` in iOS for managing follow-ups, including status transitions, region monitoring for geofences, and deep-linking to Apple Maps. Provides ETA-ranked agent recommendations.
    - **Patrol Intelligence:** Automated engine ranking plates by patrol opportunity confidence based on 30 days of sightings. Calculates confidence scores using various signals (repeat count, distinct agents, time patterns, watchlist hits).
    - **ML-Assisted Patrol Prediction:** Core ML integration in iOS for local inference on patrol data, blending rule-based scores with ML predictions for a `combined_score`.
    - **Closed-Loop Learning:** Captures structured outcomes for patrol opportunities, storing prediction-versus-outcome history. Admin evaluation dashboard provides insights into model performance and outcome distribution.
    - **Adaptive Ranking Config:** Allows dynamic adjustment of ML/rule weighting, thresholds, and priority bands based on performance.
    - **A/B Experiment Framework:** Supports controlled experiments for LPR features, with deterministic arm assignment and experiment-aware outcome recording.
    - **Policy Engine:** Defines rules for automated decision-making on experiment outcomes (promote, stop, tighten) based on performance metrics and safeguards.
    - **Controlled Automation:** Implements automated actions based on policy decisions, with guardrails, cooldowns, and post-change monitoring to prevent regressions.
    - **Document Upload / Import Workflow (Web Only):** Supports `.docx`, `.pdf`, `.doc` extraction for autofilling job creation forms. Intelligent parsing identifies key fields and performs client/customer lookups.

**12. Repo Lock (v2):**
    - Per-security-item repossession record accessible from both desktop and mobile job detail pages.
    - Button states: red `#dc2626` = no record, amber `#d97706` = Draft, green `#16a34a` = Submitted/Reviewed.
    - Desktop: Bootstrap 5 accordion modal (`repoLockModal`) with 7 sections; footer has 3 buttons: Cancel, Save Draft, Submit.
    - Mobile: full-screen overlay (`#rlOverlay`) using `<details>` elements; footer has 3 buttons: Cancel, Save Draft, Submit.
    - **Save Draft**: saves fields to `repo_lock_records` with `status='Draft'`; shows amber banner, amber button; does NOT add interactions note.
    - **Submit**: validates (repo_date, agent_name, registration or description required); saves to `repo_lock_records` with `status='Submitted'`, creates `repo_lock_queue` entry (Pending), writes formatted note to `interactions` and `job_field_notes`; shows success panel with Next Steps.
    - **Next Steps panel** (post-submit): links to VIR (`/jobs/<id>/repo-lock/<rec_id>/vir`) and Transport Instructions (`/jobs/<id>/repo-lock/<rec_id>/transport-instructions`) — placeholder templates, full implementation upcoming.
    - `_repo_lock_note(d)` helper builds a formatted plain-text summary of the entire Repo Lock record.
    - Data: `repo_lock_records` (60+ fields, `status`, `submitted_at`), `repo_lock_queue` (tracks Pending/Reviewed/Processed, `submission_count`, reviewer fields).
    - Routes: `GET /jobs/<job_id>/repo-lock/<item_id>` (JSON prefill + status), `POST .../save` (Draft), `POST .../submit` (Submitted + queue + note), `GET .../vir`, `GET .../transport-instructions`.

## External Dependencies

- **Database**: SQLite (local `axion.db` file)
- **Frontend Libraries**:
    - Bootstrap 5.3.3 (via CDN)
    - Google Maps API (for `/map` and mobile map views)
    - Leaflet.js and Leaflet.markercluster (for `/admin/lpr-sightings-map`)
- **Backend Libraries**:
    - Flask (Python web framework)
    - `python-docx` (for `.docx` document parsing)
    - `pypdf` (for `.pdf` document parsing)
    - `httpx[http2]` and `PyJWT` (for APNs delivery)
    - `antiword` (external binary, for `.doc` document parsing)
- **AI Services**:
    - OpenAI (gpt-4o-mini) for AI Update Builder (leveraging Replit's built-in access or configurable user API key)
    - Apple Core ML (for iOS-side patrol prediction inference)
- **Mobile-Specific (iOS)**:
    - WKWebView (for displaying web content within the native app)
    - SwiftUI (for native UI components)
    - CoreLocation (for GPS tracking and geofencing)
    - NWPathMonitor (for network connectivity monitoring)
    - UNUserNotificationCenter (for push notifications)
    - BackgroundTasks (for background app refresh)
    - MapKit (for ETA calculations in DispatchSheet)