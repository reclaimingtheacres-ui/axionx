# Axion Prototype

## Overview
Axion Prototype is a Flask-based field operations management application designed to streamline field operations, improve job dispatching, and enhance agent productivity. It focuses on efficient tracking of jobs, clients, customers, assets, cues, and staff. Key capabilities include comprehensive job management, role-based access, a dynamic queueing system, audit logging, monthly reporting, and robust field resource management. The system also integrates a Licence Plate Recognition (LPR) system with real-time plate lookups, watchlist hits, agent dispatch, and AI/ML-driven predictive patrol intelligence to identify high-opportunity patrol areas and automate dispatch processes. The project emphasizes mobile accessibility and data-driven decision-making, aiming to be a leading operational field and office platform.

## User Preferences
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

**1. Role-Based Access Control:** Differentiates 'Admin' and 'Agent' roles with tailored access. Includes an "Agent Draft Lockout" mechanism for managing unfinished attendance update drafts.

**2. Dynamic Queue System:** Provides an admin-only view for job management, featuring real-time updates, agent assignment badges, a queue summary bar with clickable filters, and an email queue function. It includes a comprehensive cue status lifecycle and a safeguard against leaving pages with unresolved cues.

**3. Note Workflow (Field Notes → File Notes):** Categorizes notes as `field_note` (agent scratchpad) or `file_note` (admin-published). Features include review statuses, role-based note creation, smart detection for attendance-style language on mobile, and a queue badge for pending review counts. Includes tools for managing orphaned file records.

**4. Job Scheduling:** Utilizes a unified searchable combobox for booking types across the system. Implements booking suspension upon agent reassignment to ensure clean schedules. The web-based calendar view supports day, week, month, and agenda views with date navigation, admin agent filtering, drag-and-drop rescheduling, and a detailed booking history panel.

**5. Job List Views:**
    - **Web**: Streamlined list layout with compact rows, colored status bars, consistent column alignment, pending review badges, server-side pagination, and a sticky header.
    - **Mobile**: Defaults to distance-based sorting with client-side Haversine formula for distance and background geocoding. Includes client-side and server-side search capabilities.

**6. Job Detail Views:**
    - **Web**: Side panel layout with a compact header, tab navigation (Job, Notes & Docs, Schedule, Forms, Settings), and a persistent right sidebar for job info and activity.
    - **Mobile**: Features a reorganized panel order for better accessibility, clickable customer addresses for navigation, and improved document viewer functionality.

**7. New Job Form (Web):** Single-page, two-column layout with auto-parsed vehicle details, address syncing, auto-save drafts, clone functionality, and inline entity creation. Includes an agent recommendation popup based on postcode.

**8. Mobile Job Pins Map:** Uses Leaflet.js with OpenStreetMap, displaying color-coded job pins by status. Supports agent vs. admin scope, date filter pills, a job list below the map, GPS tracking, and a comprehensive filter sheet.

**9. Add Client Workflow:** Dedicated modal for linking missing clients to jobs, with AJAX-based creation/linking, smart suggestions, and inline client card updates.

**10. Forms Module:** Grid-based dashboard for managing 7 active form types, with editable HTML templates, pre-populated fields, and PDF generation via ReportLab. Notably, the SWPI VIR form uses a template-overlay approach.

**11. Job Creation Enhancements:** Improved flow with client job number tracking, reference search, and "Clone" functionality.

**12. CSV Job Import:** Bulk import of job data via CSV, including duplicate handling, now integrated into a broader "Import & Data Management" section within Settings.

**13. GeoOp Staged Import Pipeline:** A password-gated, multi-step pipeline for importing legacy GeoOp data, featuring source-to-client mapping, agent alias system, visits CSV import, and robust attachment handling (disk scan, Azure Blob import with background processing, MD5 deduplication). Includes tools for attachment reconciliation, data repair (dates, phone numbers), and comprehensive audit logging.

**14. File Lifecycle System (Archive & Cold Storage):** A three-tier system (Active → Archived → Cold Storage) managed by `lifecycle_status` on jobs, with audit logging. Excludes archived/cold-stored jobs from active views and offers bulk archiving/restoration.

**15. Duplicate Finder:** A tool within Settings for detecting duplicate jobs and clients via database scans and CSV file scans, with AJAX-based deletion.

**16. AI Update Builder:** Guided form using OpenAI (gpt-4o-mini) to generate SWPI-style attendance updates. Features auto-filling, fact toggles, AI narrative generation, editable output, and photo attachments with client-side compression.

**17. Geomap & Agent Tracking:** Admin-only map view displaying job pins by status and live agent locations.

**18. Licence Plate Recognition (LPR) System:** Offers offline queue and background sync, push notifications for watchlist hits and dispatch, map upgrades with clustering, passive background location tracking, route/ETA intelligence, and AI-driven patrol intelligence with closed-loop learning. Includes a policy engine for controlled automation. Features robust camera stability checks, enhanced camera permission UX, a floating LPR FAB for multi-step plate entry, and a full-screen patrol mode with native and web camera fallbacks.

**19. Quick Field Notes (Mobile):** Rich note-taking directly from the job detail screen, supporting text, audio recordings, and photos.

**20. Notes Editing & Multi-Document Upload (Desktop):** Click-to-edit note rows, a full-featured edit modal with metadata, attachment management (multi-file upload, view, download, remove), and audit trails.

**21. Repo Lock (v2):** Per-security-item repossession record accessible on desktop and mobile, with draft saving, submission workflows, and PDF generation for forms.

**22. Aged Suspended / Awaiting Instructions Report:** Admin-only report for jobs in specific statuses with configurable age thresholds. Features last activity calculation, CSV/PDF export, bulk email to clients, and auto-rescheduling.

**23. Unified Authentication Routing:** Ensures consistent login/logout experiences across web and mobile, redirecting users to appropriate login pages based on device detection. Includes vertical centering of login card on mobile.

**24. Biometric Login (Face ID / Touch ID):** Backend support for mobile authentication tokens, iOS native integration for Face ID/Touch ID, and secure token management. Includes password autofill attributes and global photo upload compression with HEIC/HEIF support. Critical address data consistency and geocode sync are implemented across the platform. New features include job type upgrades, default job types, installment field renaming, customer popup phone/email functionality, asset types with "No Asset" handling, and third-party referral fields. It also features a single login screen architecture and robust camera permission/capture services via native bridges.

**25. Internal Messaging System:** Staff messaging with job-linked and direct conversations. Features system sender for automated messages, a detailed audit trail, bulk select/delete, read-based auto-cleanup, desktop/mobile layouts, new message modals with multi-recipient broadcast, unread badges, and push notifications. Also includes auto-notifications on job assignment, new job exit guards, visit type sync, and "reallocated" file notes.

**26. Customer & Client List Search:** Search functionality for both customer and client lists with comprehensive querying, partial matching, case-insensitivity, and search persistence.

**27. Customer Call/SMS Actions:** Inline call and SMS buttons for phone numbers on customer and job detail pages.

**28. Customer Edit Modal (Job Detail):** Admin-only modal for editing customer details directly from the job page via AJAX, including a dedicated "Job Location to Attend" field.

**29. Search Clear Buttons:** Clear buttons implemented on all search inputs for improved usability.

**30. Document Viewer Browser History Fix:** Modal-based document viewer correctly manages browser history to prevent unintended navigation.

**31. Route Planner Module:** Comprehensive route planning on web and mobile. Features include filters, start/end point selection, route optimization modes, job selection, Google Maps integration, and agent assignment.

**32. Multi-Customer per Job:** Jobs can now have multiple linked customers with individual roles. Customer roles expanded to: Primary, Co-Borrower, Guarantor, Director, Partner, Spouse, Occupant, Third Party in Possession, Other (with custom label). New Job form includes "+ Add Another Customer" blocks with typeahead search + role selection. Job detail page has per-customer "Edit Role" button opening a modal to change or customise any customer's role. "Other" role values are stored as "Other: <custom text>" in the DB and displayed with the custom label only. Backend: `job_customer_add` route handles `role_other`; new `job_customer_role` route (`POST /jobs/<id>/customers/<jc_id>/role`) updates existing link roles; `_job_create_inner()` processes `extra_customer_ids[]` + `extra_customer_roles[]` form arrays.

**33. Per-Item Arrears & Costs on Additional Securities:** Each `job_items` record now stores its own `arrears_cents` and `costs_cents` columns. Display: vehicle/motorcycle/trailer cards now show the item `description` field (previously invisible) plus an inline Arrears/Costs row when values are present. Input surfaces updated: inline Edit form, "+ Add Security" form (job_detail), New Job asset rows (asset_arrears[]/asset_costs[]), and clone-data endpoint + clone-apply JS. Mobile job_detail also shows per-item arrears/costs in the asset card. Schema migration via `add_column_if_missing`.

## External Dependencies

- **Database**: SQLite
- **Frontend Libraries**: Bootstrap 5.3.3, Google Maps API, Leaflet.js, Leaflet.markercluster
- **Backend Libraries**: Flask, `python-docx`, `pypdf`, `httpx[http2]`, `PyJWT`, `olefile`, `antiword`, `pillow-heif`
- **AI Services**: OpenAI (gpt-4o-mini), Apple Core ML
- **Mobile-Specific (iOS)**: WKWebView, SwiftUI, CoreLocation, NWPathMonitor, UNUserNotificationCenter, BackgroundTasks, MapKit