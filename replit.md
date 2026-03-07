# Axion Prototype

## Overview
Axion Prototype is a Flask-based field operations management application designed to streamline field operations, improve job dispatching, and enhance agent productivity. It focuses on efficient tracking of jobs, clients, customers, assets, cues, and staff. Key capabilities include comprehensive job management, role-based access, a dynamic queueing system, audit logging, monthly reporting, and robust field resource management. The system also integrates a Licence Plate Recognition (LPR) system with real-time plate lookups, watchlist hits, agent dispatch, and AI/ML-driven predictive patrol intelligence to identify high-opportunity patrol areas and automate dispatch processes. The project emphasizes mobile accessibility and data-driven decision-making.

## User Preferences
No explicit user preferences were provided in the original `replit.md` file. The document primarily describes system features and technical implementation details.

## System Architecture

### Core Technologies
- **Backend**: Python 3.11 with Flask 3.0.3
- **Database**: SQLite (`axion.db`)
- **Frontend**: Jinja2 templates, Bootstrap 5.3.3, and custom JavaScript.
- **Mobile Wrapper**: Native iOS application (SwiftUI, WKWebView) for mobile web routes.

### Design Patterns & Features

**1. Role-Based Access Control:** Differentiates 'Admin' and 'Agent' roles with tailored access to features like job visibility, dashboards, cues, assignment boards, reports, and user management.

**2. Dynamic Queue System:** Provides an admin-only view of 'Overdue', 'Currently Due', and 'Agent Notes — Pending Review' items, enabling direct email composition and job updates.

**3. Cues System:** Manages `cue_items` (scheduled tasks) with properties like date, visit type, priority, and agent assignment. Supports daily cue access for agents and drag-and-drop assignment for admins, with automatic cue generation for overdue or upcoming schedules.

**4. Audit Log:** Logs all significant system actions, accessible via the admin dashboard.

**5. Field Resources Management:** Centralized management of Tow Operators and Auction Yards with interactive modals for adding, editing, and deleting entries.

**6. Forms Module:** Grid-based dashboard for 7 active form types (SWPI VIR, Transport Instructions, Voluntary Surrender, Form 13, Wise VIR, Auction Letter, Tow Letter). Forms are editable HTML with pre-populated fields saving to DB before PDF generation via ReportLab. Signatures captured live via canvas pads — NOT stored in DB. After every PDF is generated, it is auto-saved to job_documents and a note added to job_field_notes. Filename format: "[JobNumber] - [Form Name] - [DD-MM-YYYY].pdf". Complete Repo Pack (GET) merges unsigned reference copies and also attaches to the job.

**7. Job Creation Enhancements:** Improved job creation flow with client job number tracking, reference search, and a "Clone" functionality for pre-filling new job forms.

**8. CSV Job Import:** Allows bulk import of job data via CSV files, with duplicate handling.

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

**12. Repo Lock (v2):** Per-security-item repossession record accessible on desktop and mobile. Features draft saving and submission workflows, generating formatted notes and linking to PDF generation for VIR, Transport Instructions, and other forms. Includes signature capture and PDF generation via `pdf_gen.py`.

## External Dependencies

- **Database**: SQLite
- **Frontend Libraries**: Bootstrap 5.3.3, Google Maps API, Leaflet.js, Leaflet.markercluster
- **Backend Libraries**: Flask, `python-docx`, `pypdf`, `httpx[http2]`, `PyJWT`, `antiword` (external binary)
- **AI Services**: OpenAI (gpt-4o-mini), Apple Core ML
- **Mobile-Specific (iOS)**: WKWebView, SwiftUI, CoreLocation, NWPathMonitor, UNUserNotificationCenter, BackgroundTasks, MapKit