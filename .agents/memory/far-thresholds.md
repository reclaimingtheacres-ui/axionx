---
name: FAR thresholds per activity type
description: Field Activity Reporting delay-reason thresholds differ by activity type; must not use a single constant.
---

## Rule
FAR delay-reason thresholds are per-activity-type, not a single global value.

| Activity type | Threshold |
|---|---|
| Repo Lock (repossession) | 30 minutes |
| General field activity | 8 hours (480 min) |

**Why:** The product owner confirmed these differ. A 12-hour (or any single) constant is wrong and was rejected during review.

## How to apply
- Constants live in `_FAR_THRESHOLDS_MINUTES = {"repo": 30, "general": 480}` near line 7499 in `app.py`.
- Helper `_far_threshold_minutes(note_type, job_type)` returns the correct value for a given note.
- Management SQL uses a CASE expression so each row is evaluated against its own threshold:
  `CASE n.note_type WHEN 'Repo Lock' THEN 30 ELSE 480 END`
- Client-side JS uses the general threshold (8 h / 480 min) because the UI only surfaces general field notes; Repo Lock threshold is enforced server-side via the auto-derived activity_occurred_at.
- To add a new activity type: add a key to `_FAR_THRESHOLDS_MINUTES`, update `_far_threshold_minutes()`, and extend the SQL CASE expression.

## Repo Lock specifics
- `repo_lock_submit()` derives `activity_occurred_at` from `repo_date` + `start_time` already in the form — no new UI field required.
- `reporting_delay_minutes` is computed via `_far_calc_delay()` and inserted into `job_field_notes` at submission time.
- `delay_reason` is not collected on the Repo Lock form (no UI for it); the 30-min threshold flags it in the dashboard for admin review.
