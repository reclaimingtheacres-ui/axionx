---
name: Agent attribution — last_assigned_user_id
description: Why completed/invoiced jobs lose their agent assignment and how reporting must use last_assigned_user_id instead.
---

## The rule

`assigned_user_id` is cleared to NULL in exactly two places when a job reaches Completed, Invoiced, or Cancelled:
- `job_status_update` (POST /jobs/<id>/status) — line ~7360
- `job_update` (POST /jobs/<id>/update) — line ~8661

**Why:** By design — once closed, a job should not appear on any agent's active workload.

**Consequence:** Any reporting query that uses `assigned_user_id IS NOT NULL` on terminal-status jobs will return near-zero results.

## The fix

`last_assigned_user_id INTEGER` on the `jobs` table captures the agent before the clear:

```python
cur.execute(
    "UPDATE jobs SET assigned_user_id = NULL, "
    "last_assigned_user_id = COALESCE(last_assigned_user_id, ?), "
    "updated_at = ? WHERE id = ?",
    (old_agent, now, job_id)
)
```

`COALESCE(last_assigned_user_id, ?)` ensures a later Invoiced transition doesn't overwrite a backfilled value.

## Reporting attribution model

| Metric | Attribution column |
|---|---|
| Completed files | `COALESCE(last_assigned_user_id, assigned_user_id)` |
| Repossessions | `COALESCE(repo_lock_records.agent_user_id, last_assigned_user_id, assigned_user_id)` |
| Active files | `assigned_user_id` (unchanged) |
| Attendances/re-attendances | `schedules.assigned_to_user_id` (never cleared) |

## Statuses that do NOT clear assigned_user_id

Repossessed, Surrendered, Closed, Closed Field Call are NOT in the clear list. Only Completed, Invoiced, Cancelled trigger the NULL.

## Historical backfill

One-time backfill in `_startup_migrate` (idempotent, WHERE IS NULL guard):
Priority: (1) repo_lock_records.agent_user_id → (2) last schedule's assigned_to_user_id → (3) last field_note's created_by_user_id.

## No Update > 7 Days fix

Add `AND n.note_category = 'field_note'` to the NOT EXISTS subquery so admin correspondence, client emails, document uploads, and system notes do not reset the agent activity counter.
