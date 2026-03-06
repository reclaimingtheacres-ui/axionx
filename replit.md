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
  mobile/               Canonical mobile templates (white/light theme)
    base.html           Base layout — 4-tab bottom nav (Schedule/Jobs/Map/Settings)
    login.html          Standalone login (no nav, iOS safe-area)
    job_detail.html     Read-only job detail (Call/SMS tap buttons, assets, draft banner)
    map.html            Google Maps + date filters + GPS tracking + job list
    jobs.html              Full-featured jobs list: search, filter sheet, client-side sort + distance
    settings.html          Mobile prefs (jobs sort/scope/completed, distance unit, GPS, status toggle)
    tow_operators.html     Tow operators list with tap-to-call buttons
    tow_operator_form.html Create tow operator (company, contact, phones, address, notes)
    auction_yards.html     Auction yards list with tap-to-call buttons
    auction_yard_form.html Create auction yard (name, contact, phones, address, notes)
  m/                    Mobile page templates (all extend mobile/base.html)
    today.html          Today's schedule (cues + schedules, draft alerts)
    update_builder.html Mobile AI update builder (shares backend generate/save endpoints)
```

## iOS Wrapper (ios/)

Native iPhone app wrapping the /m/* mobile web routes. Open `ios/AxionX.xcodeproj` in Xcode 15+.

SwiftUI App lifecycle, UIViewRepresentable WKWebView, NWPathMonitor connectivity, CoreLocation WhenInUse.

```
ios/
├── AxionX.xcodeproj/               Xcode project + shared scheme
└── AxionX/
    ├── AxionXApp.swift             @main SwiftUI entry + AppDelegate push stub
    ├── ContentView.swift           Splash → connectivity check → WebView root
    ├── Config/
    │   ├── AppConfig.swift         Debug/Release URL, entry path, splash timing
    │   └── AllowedDomains.swift    Trusted hosts + routing rules
    ├── WebView/
    │   ├── AxionWebView.swift      UIViewRepresentable + WebViewStore
    │   ├── WebViewContainer.swift  SwiftUI container + offline overlay
    │   └── WebViewNavigationDelegate.swift  WKNavigationDelegate + WKUIDelegate
    ├── Views/
    │   ├── SplashView.swift        White splash with AxionX branding
    │   └── OfflineView.swift       Retry screen (wifi.slash icon)
    ├── Services/
    │   ├── ConnectivityMonitor.swift  NWPathMonitor @ObservableObject
    │   └── LocationPermissionHelper.swift  WhenInUse only
    ├── Assets.xcassets/            AppIcon + AccentColor + LaunchLogo
    ├── LaunchScreen.storyboard     OS-level splash before SwiftUI
    └── Info.plist                  Portrait-only, light mode, HTTPS ATS, location usage
```

**To build:** edit `Config/AppConfig.swift` debug URL → set signing team → Product → Archive → TestFlight

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

## LPR (Licence Plate Recognition) — Stages 1–7

Mobile LPR system for iOS field agents. Backend in `app.py`, mobile templates under `templates/mobile/`, admin templates at root, iOS code under `ios/AxionX/`.

**Stage 8 — Offline Queue, Background Sync, Idempotency (current)**

**DB change**: `lpr_sightings.client_action_id TEXT` column added (idempotency key).

**Backend idempotency**:
- `POST /m/api/lpr/sighting` checks `client_action_id` + `user_id` before insert; returns existing record if already saved (no duplicate created on retry). Returns `{"ok": true, "sighting_id": N, "duplicate": true}` on duplicate.
- `POST /m/api/device/register` already idempotent via `ON CONFLICT` constraint.

**New routes**:
- `GET /m/api/lpr/sync` — returns `{unread_notification_count, assigned_followup_count, server_time}` for the current agent
- `GET /m/api/lpr/assigned-followups` — returns `{count, items[]}` of open follow-ups assigned to the current agent

**iOS new files**:
- `ios/AxionX/Offline/OfflineQueue.swift` — thread-safe NSLock + UserDefaults-backed queue; `OfflineQueueItem` stores `clientActionId, actionType, payload[String:String], createdAt, retryCount, lastError, status`. Action types: `save_sighting`, `register_device`, `mark_notifications_read`. Sensitive data (customer name, address, finance) never stored.
- `ios/AxionX/Offline/SyncManager.swift` — `@MainActor ObservableObject` singleton; uses `NWPathMonitor` to auto-sync when connectivity returns; `setWebView()` wires WKWebView session for cookie-authenticated requests and triggers immediate drain of pending items; `syncNow()`, `retryFailed()`, `enqueueSaveSighting/enqueueDeviceRegister/enqueueMarkNotificationsRead()` helpers.
- `ios/AxionX/Views/SyncStatusView.swift` — SwiftUI sheet with pending/failed/recent-success sections; per-item retry and "Retry All" / "Sync Now" actions; follows environmentObject pattern.

**iOS updated files**:
- `LPRResultSheet.swift` — `doSaveSighting()` generates `clientActionId` (UUID), sends it with every save attempt; on network failure, safe payload is queued via `SyncManager.shared.enqueueSaveSighting()`; new `savedQueued` state shows orange "Saved offline" banner. `LPRAPIClient` gains `postAction(path:body:webView:)` (async Bool) and `getJSON(path:webView:completion:)` (cookie-authenticated GET).
- `WebViewContainer.swift` — calls `SyncManager.shared.setWebView()` in `wireDelegate()`; shows orange/red pill badge at bottom-left when `pendingCount + failedCount > 0`; tapping badge opens `SyncStatusView` sheet.
- `AxionXApp.swift` — `applicationDidBecomeActive` now also calls `await SyncManager.shared.syncNow()`.
- `PushNotificationService.swift` — `uploadToken()` enqueues via `SyncManager.enqueueDeviceRegister()` if direct upload fails (fallback path for cold-start before WKWebView session is established).
- `AxionXApp.swift` — `WindowGroup` passes `.environmentObject(SyncManager.shared)` so all child views can access it.

**pbxproj IDs used**:
- `OfflineQueue.swift`: fileRef `F100000000000000000028`, buildFile `F100000000000000000029`
- `SyncManager.swift`: fileRef `F10000000000000000002A`, buildFile `F10000000000000000002B`
- `SyncStatusView.swift`: fileRef `F10000000000000000002C`, buildFile `F10000000000000000002D`
- Offline group: `G100000000000000000009` (next available group ID)

**Stage 7 — Push Notifications, Dispatch, Proximity**

**New DB tables**: `lpr_device_tokens`, `lpr_notifications`, `lpr_followups`, `lpr_proximity_rules`

**APNs delivery**: `_apns_send()` uses PyJWT + httpx[http2]. Requires env vars: `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_PRIVATE_KEY` (.p8 content), `APNS_BUNDLE_ID` (default `com.axionx.ios`), `APNS_SANDBOX` (default `1`). Gracefully no-ops if not configured; in-app notifications still stored in DB.

**Notification triggers**:
- Urgent/high watchlist hit at lookup → notify all admin/both users
- Sighting saved with watchlist_hit or escalated → notify admins + proximity check
- Proximity zone match (watchlist sighting inside defined radius) → separate zone alert to admins
- Sighting reviewed → notify the original agent
- Follow-up assigned → notify the assigned agent (push + in-app)

**New routes**:
- `POST /m/api/device/register` — store/update APNs device token
- `GET /m/lpr/notifications` — agent notification feed (marks all read on open)
- `POST /m/api/lpr/notifications/read` — mark all read
- `GET /m/api/lpr/notifications/unread-count` — JSON badge count
- `GET /admin/lpr-proximity` — manage proximity zones
- `POST /admin/lpr-proximity/add` — add zone (name, lat, lng, radius_m, priority)
- `POST /admin/lpr-proximity/<id>/toggle` — activate/deactivate
- `POST /admin/lpr-sightings/<id>/followup` — create follow-up dispatch record

**iOS additions**:
- `ios/AxionX/Services/PushNotificationService.swift` — permission request, token upload, badge refresh
- `ios/AxionX/AxionX.entitlements` — `aps-environment: development` (flip to `production` for App Store)
- `AxionXApp.swift` — activates push registration, `UNUserNotificationCenterDelegate` implemented, foreground banners enabled, notification tap navigates to `/m/lpr/notifications`
- `WebViewContainer.swift` — `.onReceive(.axionOpenNotifications)` navigates web view to notifications screen

**Helper functions**: `_haversine_m()`, `_proximity_check()`, `_notify_user()`, `_notify_admins()`

**Templates**: `lpr_proximity.html` (admin zone CRUD), `mobile/lpr_notifications.html` (agent feed), `lpr_sightings.html` updated with Follow-up modal + Zones nav link, `mobile/lpr_search.html` updated with Alerts header link.

---

## LPR Stage 9 — Dispatch Intelligence & Map Upgrade

**New dispatch intelligence helpers** (`app.py`):
- `_dist_label(metres)` — human-readable distance string (e.g. "450 m", "2.3 km")
- `_nearest_agents(lat, lng, conn, limit=3, max_hours=8)` — agents with recent GPS updates, sorted by distance from sighting
- `_lpr_repeat_info(reg_norm, lat, lng, conn, ...)` — total/nearby/multi-agent repeat sightings of the same plate (last 30 days, 1 km radius)
- `_lpr_dispatch_score(result_type, watchlist_h, escalated, repeat_info, nearest_agents, prox_hits)` — score-based priority band (Urgent/High/Medium/Low) + recommended action string

**New route**: `GET /admin/lpr-sightings/<id>/intelligence` — returns JSON with `nearest_agents`, `repeat_info`, `proximity_hits`, `dispatch_score`. No customer/finance data in payload.

**Updated routes**:
- `admin_lpr_sightings_map` — geojson features now include `plate_count` (30-day repeat count), `reviewed`, `follow_up` fields; also passes `agents_json` (agent pins for last 8 h)
- `admin_lpr_sightings` — rows now include `plate_count` via CTE subquery

**Map rewrite** (`lpr_sightings_map.html`):
- Leaflet.markercluster 1.5.3 with custom cluster icons (priority-colour-coded: purple=watchlist/escalated, red=hotspot, amber=restricted, blue=default)
- Floating toolbar: filter chips (All / Watchlist / Escalated / Unreviewed / Restricted / Hotspot 3+), plate search input, Agents toggle
- Agent location pins (green initials circles) pulled from `agent_locations` table, togglable
- Enhanced popups: repeat-count badge (×N), review status, "Seen N times in 30 days" note
- JS-only filtering (no server round-trip); search debounced at 280 ms

**Sightings table update** (`lpr_sightings.html`):
- Registration column shows red ×N badge when plate_count ≥ 2
- Review and Follow-up modals expanded to `modal-lg` with dispatch intelligence panel
- Intelligence panel loads via AJAX on modal open: priority badge, recommended-action alert box, nearest agents list, repeat-sightings summary
- Follow-up modal auto-selects the nearest agent in the assignee dropdown

---

## LPR Stage 10 — Passive Background Location & Agent Dispatch Awareness

### Backend additions

**New table** `agent_movement` (`id, user_id, latitude, longitude, captured_at, received_at, source, accuracy_m, battery_state, context`) — append-only movement history; no customer/finance data.

**New route** `POST /m/api/location/ping` — inserts a row into `agent_movement` and upserts `agent_locations` for backward compatibility. Accepts: `lat, lng, accuracy, captured_at, source, battery_state, context`.

**New route** `GET /admin/lpr/agent-map` — renders `lpr_agent_map.html` with last-known agent positions + 10-ping trail per agent from the last 8 hours.

**Updated** `_nearest_agents()` — queries `agent_movement` (latest ping per agent, last 8 h) as primary source; falls back gracefully to `agent_locations`. Returns `source` and `battery` fields alongside distance.

**Updated** `admin_lpr_sightings_map` — agent pins now built from `agent_movement` (with fallback to `agent_locations`). Agent source/battery available in pin data.

### iOS additions

**`AgentLocationService.swift`** (Services group) — CLLocationManager wrapper with three modes:
- `offDuty` — all location monitoring stopped
- `available` — `startMonitoringSignificantLocationChanges()` (low-power, works in background)
- `activeJob` — `startUpdatingLocation()` with 50 m distance filter + 30-min auto-downgrade timer
- Captures battery state (`UIDevice.batteryState`) and app context (foreground/background) with each ping
- Delivers via `SyncManager.shared.enqueueLocationPing(...)` — always offline-safe through queue

**`FieldStatusManager.swift`** (Services group) — `@MainActor ObservableObject` singleton:
- Persists field status in `UserDefaults` (`com.axionx.field_status_v2`)
- Restores `available` on restart if last status was `activeJob` (activeJob never survives restart)
- Drives `AgentLocationService.apply(_:)` on every status change
- `downgradeActiveJob()` called by `AgentLocationService` timer after 30 min

**`FieldStatusView.swift`** (Views group) — compact 3-segment pill control:
- Segments: Off Duty (grey) / Available (green) / Active Job (blue)
- Shown as a floating overlay at the bottom centre of all `/m/lpr*` pages inside `WebViewContainer`
- Rises above the sync badge when pending items are present

**`OfflineQueue.swift`** — added `"location_ping"` action label

**`SyncManager.swift`** — added `enqueueLocationPing(lat:lng:accuracy:battery:context:source:capturedAt:)` helper; added `"location_ping"` case in `processItem` routing to `POST /m/api/location/ping`. Location pings are transparent to the badge counter.

**`AxionXApp.swift`** — imports `BackgroundTasks`; registers `BGAppRefreshTask` with identifier `com.axionx.sync`; initialises `FieldStatusManager.shared` on launch; passes `.environmentObject(FieldStatusManager.shared)` to `ContentView`; background task handler calls `SyncManager.shared.syncNow()` then reschedules.

**`WebViewContainer.swift`** — accepts `@EnvironmentObject var fieldStatusManager: FieldStatusManager`; shows `FieldStatusView()` as a floating bottom-centre overlay on LPR pages.

**`Info.plist`** — added `NSLocationAlwaysAndWhenInUseUsageDescription`, `NSLocationAlwaysUsageDescription`, `UIBackgroundModes` (`location`, `fetch`, `processing`), `BGTaskSchedulerPermittedIdentifiers` (`com.axionx.sync`).

**`project.pbxproj`** — new IDs 2E/2F (AgentLocationService), 30/31 (FieldStatusManager), 32/33 (FieldStatusView); Services and Views groups updated; Sources build phase updated.

### New template `lpr_agent_map.html`
- Leaflet map showing last-known position of each active agent (last 8 h)
- Agent pins are colour-coded by field status source (blue=active_job, green=available, grey=unknown)
- Faded trail dots + dashed polyline show recent movement (up to 9 prior pings)
- Popup shows: agent name, last ping time, status source label, battery icon
- Empty-state message when no agents active
- Accessible from Sightings Table and Sightings Map via "👥 Agents"/"👥 Agent Map" buttons
