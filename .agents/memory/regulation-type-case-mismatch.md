---
name: regulation_type case mismatch (fixed)
description: Root cause and fix for regulation_type/payment_frequency data loss on jobs
---

## Rule
`regulation_type` canonical values are **title case**: `Regulated`, `Unregulated`, `N/A`.

**Why:** The lender panel form in `job_detail.html` compares `job.regulation_type == rt` against `['Regulated','Unregulated','N/A']`. Storing uppercase (`REGULATED`/`UNREGULATED`) caused no option to pre-select, so any subsequent lender form save would blank the value.

## What was fixed (2026-05-26)
- `app.py` ACS parser (lines ~2311-2312): `"UNREGULATED"` → `"Unregulated"`, `"REGULATED"` → `"Regulated"`
- `app.py` Wise parser (lines ~2461-2462): same
- `_startup_migrate()`: one-time `UPDATE jobs SET regulation_type='Regulated' WHERE regulation_type='REGULATED'` (and Unregulated)
- `job_new.html` regulation_type `<option>` elements: added explicit `value=` attrs, changed text to title case, added N/A option, updated Jinja pre-selection to use `| upper` comparison
- `geoop_import.py` (update, insert, backfill, repair-due-dates): `_pmt_freq = "" when no NMPD` → `None`, preventing empty-string from overwriting existing `payment_frequency` as NULL

## How to apply
- Any new parser or import route writing `regulation_type` must use title case values
- The lender form `job_detail.html` is the canonical source for allowed values; keep it consistent with `job_new.html`
- `payment_frequency` falsy default must be `None` (not `""`) in all import paths so COALESCE/CASE WHEN patterns preserve existing DB values
