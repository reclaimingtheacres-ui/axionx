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
- **Role-Based Access Control:** Differentiates 'Admin' and 'Agent' roles with tailored access, including an "Agent Draft Lockout" mechanism.
- **Dynamic Queue System:** Admin-only view for job management with real-time updates, agent assignment, queue summary, email queue, and cue status lifecycle management.
- **Note Workflow:** Categorizes notes as `field_note` (agent) or `file_note` (admin), with review statuses, role-based creation, and attendance-style language detection.
- **Job Scheduling:** Unified searchable combobox for booking types, booking suspension on reassignment, and a web-based calendar view with various display modes and drag-and-drop rescheduling.
- **Job List Views:** Streamlined web layout with compact rows, status bars, pagination, and sticky headers. Mobile defaults to distance-based sorting with client-side geocoding and search.
- **Job Detail Views:** Side panel web layout with tabs and a persistent sidebar. Mobile features reorganized panels and improved document viewing.
- **New Job Form (Web):** Single-page layout with auto-parsed vehicle details, address syncing, auto-save drafts, clone functionality, and agent recommendations.
- **Mobile Job Pins Map:** Leaflet.js with OpenStreetMap, displaying color-coded job pins, agent vs. admin scope, date filters, and GPS tracking.
- **Add Client Workflow:** Modal for linking clients with AJAX-based creation/linking and smart suggestions.
- **Forms Module:** Grid-based dashboard for managing 7 active form types with editable HTML templates, pre-populated fields, and PDF generation.
- **Job Creation Enhancements:** Improved flow with client job number tracking, reference search, and "Clone" functionality.
- **CSV Job Import:** Bulk import of job data with duplicate handling, integrated into Settings.
- **GeoOp Staged Import Pipeline:** Password-gated, multi-step pipeline for importing legacy GeoOp data, including source-to-client mapping, agent alias system, visits CSV import, and robust attachment handling.
- **File Lifecycle System (Archive & Cold Storage):** Three-tier system (Active → Archived → Cold Storage) with audit logging and bulk management.
- **Duplicate Finder:** Tool for detecting duplicate jobs and clients via database and CSV scans.
- **AI Update Builder:** Guided form using OpenAI (gpt-4o-mini) to generate SWPI-style attendance updates with auto-filling, fact toggles, AI narrative, and photo attachments.
- **Geomap & Agent Tracking:** Admin-only map view displaying job pins and live agent locations.
- **Licence Plate Recognition (LPR) System:** Offline queue, background sync, push notifications for watchlist hits, map upgrades, passive location tracking, route intelligence, and AI-driven patrol intelligence.
- **Quick Field Notes (Mobile):** Rich note-taking with text, audio, and photos directly from job detail.
- **Notes Editing & Multi-Document Upload (Desktop):** Click-to-edit notes, full-featured edit modal, attachment management, and audit trails.
- **Repo Lock (v2):** Per-security-item repossession record accessible on desktop and mobile, with draft saving, submission workflows, and PDF generation.
- **Aged Suspended / Awaiting Instructions Report:** Admin-only report for jobs in specific statuses with configurable age thresholds, export options, and bulk actions.
- **Unified Authentication Routing:** Consistent login/logout experiences across web and mobile, device-based redirects, and biometric login support (Face ID/Touch ID).
- **Internal Messaging System:** Staff messaging with job-linked and direct conversations, automated messages, audit trails, unread badges, and push notifications.
- **Customer & Client List Search:** Comprehensive search functionality for customer and client lists.
- **Customer Call/SMS Actions:** Inline call and SMS buttons on customer and job detail pages.
- **Customer Edit Modal (Job Detail):** Admin-only modal for editing customer details via AJAX.
- **Search Clear Buttons:** Implemented on all search inputs.
- **Document Viewer Browser History Fix:** Modal-based document viewer correctly manages browser history.
- **Route Planner Module:** Comprehensive web and mobile route planning with filters, optimization, Google Maps integration, and agent assignment.
- **Multi-Customer per Job:** Supports multiple linked customers per job with individual roles.
- **Per-Item Arrears & Costs on Additional Securities:** Each `job_items` record stores its own `arrears_cents` and `costs_cents`.
- **Photo Upload Performance (Mobile Quick Note):** Photos written to local disk first, then synced to Azure Blob Storage in a background thread.
- **Repo Lock Form Fixes:** Improved error handling for `repo_lock_save` and `repo_lock_submit`, with inline error display.
- **Form 13 PDF Response Contract:** JSON-only POST contract for Form 13 save/generate, returning structured success/error data.
- **Transport Instructions Tow Operator Phone Persistence:** `tow_phone` persisted as a first-class field in Repo Lock records.
- **Internal Message Notification Hardening:** APNs alerts with rich content, device token management, and per-message/per-recipient logging.
- **Recovery Targets Module:** Standalone module for loss recovery/LPR repossession targets with dedicated child tables, document upload, and mobile search.
- **Mobile Repo Lock Document Flow:** Consistent JSON generation for VIR, Form 13, and Transport Instructions, providing mobile-safe preview URLs for native Quick Look.
- **Admin Navigation Tidy-Up:** AI Draft Cleanup integrated into Admin Settings; Recovery Targets moved to Admin menu.
- **SMTP Configuration Hardening:** Centralized runtime SMTP resolver with robust error handling and logging.
- **iOS LPR Camera Overlay Suppression:** Native iOS `WebViewContainer` suppresses floating buttons, status pills, banners, and sync badges during active LPR camera contexts.
- **Demo Environment (AXIONX_DEMO_MODE):** Fully isolated demo mode with separate database, intercepted external communications, visible banner, watermarked PDFs, and guided workflow.
- **Demo Deployment Infrastructure:** `startup_demo.sh` (Azure App Service); `startup_demo_replit.sh` (Replit fork — auto-seeds DB, starts scheduler, port 5000); `demo_scheduler.py` (nightly auto-reset, `AXIONX_DEMO_RESET_CRON` env var, dual safety guard); `/demo/health` JSON endpoint; `.github/workflows/deploy-demo.yml` GitHub Actions workflow for Azure; `DEMO_DEPLOYMENT.md` fork/configure guide; root `/` redirects to `/demo` when `DEMO_MODE=true`.

## External Dependencies
- **Database**: SQLite (`axion.db`, `axion_demo.db`)
- **Frontend Libraries**: Bootstrap 5.3.3, Google Maps API, Leaflet.js, Leaflet.markercluster
- **Backend Libraries**: Flask, `python-docx`, `pypdf`, `httpx[http2]`, `PyJWT`, `olefile`, `antiword`, `pillow-heif`
- **AI Services**: OpenAI (gpt-4o-mini), Apple Core ML
- **Mobile-Specific (iOS)**: WKWebView, SwiftUI, CoreLocation, NWPathMonitor, UNUserNotificationCenter, BackgroundTasks, MapKit