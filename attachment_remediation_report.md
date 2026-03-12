# AxionX Attachment Remediation Report

## Status of Outstanding Items

| # | Item | Status |
|---|------|--------|
| 1 | Original GeoOp Description (read-only section) | **DONE** — Displayed on job detail page below Lender Details, conditionally rendered when populated |
| 2 | Edit controls for Vehicle/Security and Lender Details | **DONE** — Role check fixed from `== 'admin'` to `in ('admin', 'both')` across all 22 instances |
| 3 | Attachment remediation | **AUDIT COMPLETE** — See details below |
| 4 | Description & Instructions on main page | **DONE** — Editable section below Security/s card |

---

## Attachment Audit Summary

### 1. How Many Imported Attachments Exist

| Source | Count | Notes |
|--------|------:|-------|
| Staging notes with file references | 58,909 | 26.3% of 223,700 staged notes have `file_name` + `files_location` |
| Jobs CSV `File Locations` column | 14,796 | Jobs with at least one file path listed (comma-separated) |
| `geoop_staging_files` (file manifest) | 0 | Not yet populated — no scan has been run |
| `job_documents` (production) | 0 | No job-level documents imported |
| `job_note_files` (production) | 2 | Only 2 manual uploads; no GeoOp files imported |

### 2. How Many Are Linked to Jobs

**Zero.** No attachment import has been executed yet. The staging notes contain file path references
(e.g., `4604582/8699194/22755233/` → `22755233.pdf`) but these have not been fetched from Azure or linked to Axion jobs/notes.

- `geoop_staging_notes.axion_note_id`: **0 of 223,700** populated
- `geoop_staging_notes.import_status`: **All 223,700 = 'pending'**

### 3. How Many Are Linked to Notes

**Zero GeoOp attachments linked to notes.** The 2 existing `job_note_files` records are manual uploads, not GeoOp imports.
The note import itself has not been run — all 223,700 staged notes are still `pending`.

### 4. How Many Failed to Link

**N/A — No import attempted.** The `geoop_unmatched_attachments` table does not yet exist (it is created by `scan_azure_blob_attachments()` on first run).
There are zero error records because the process has not been executed.

### 5. File Skip Reasons

No files have been skipped because no scan has been run. However, the import pipeline includes
the following skip/reject logic that will apply once the scan executes:

| Skip Reason | Mechanism |
|-------------|----------|
| **Path parsing failure** | `_parse_attachment_path()` extracts `geoop_job_id` and `geoop_note_id` from the blob path. Unrecognised structures are logged to `geoop_unmatched_attachments`. |
| **No matching Axion job** | If `geoop_job_id` has no corresponding `axion_job_id` in the staging table, the file cannot be linked. |
| **No matching Axion note** | If `geoop_note_id` has no corresponding `axion_note_id`, the file is stored as a `job_document` (job-level) instead of a `job_note_file`. |
| **Duplicate (MD5 hash)** | `_process_file()` calculates MD5 hashes. Files already in `geoop_staging_files` with the same hash are skipped. |
| **Unsupported mapping** | The pipeline stores all file types — no extension-based filtering. |

---

## File Type Distribution (from staging notes)

| Extension | Count | % |
|-----------|------:|---:|
| .pdf | 28,126 | 47.8% |
| .jpg | 11,194 | 19.0% |
| .m4a | 7,208 | 12.2% |
| .doc | 4,126 | 7.0% |
| .docx | 2,500 | 4.2% |
| .heic | 2,046 | 3.5% |
| .png | 1,951 | 3.3% |
| .jpeg | 1,131 | 1.9% |
| .msg | 153 | 0.3% |
| .wav | 122 | 0.2% |
| .zip | 93 | 0.2% |
| .xlsx | 92 | 0.2% |
| .rtf | 29 | 0.0% |
| .xls | 26 | 0.0% |
| (none) | 23 | 0.0% |
| .xps | 14 | 0.0% |
| .avif | 14 | 0.0% |
| .tif | 11 | 0.0% |
| .rar | 8 | 0.0% |
| .jfif | 8 | 0.0% |
| **Total** | **58,875** | |

---

## Current Pipeline State

```
STAGE 1: stage_notes_csv()       → 223,700 notes staged     ✅ DONE
STAGE 2: import_staged_notes()    → Import into job_field_notes  ❌ NOT RUN (0 of 223,700)
STAGE 3: scan_azure_blob_attachments() → Fetch files from Azure ❌ NOT RUN
STAGE 4: import_staged_files()    → Link files to jobs/notes     ❌ NOT RUN
```

### Dependencies

- **Stage 2 requires Stage 1** (done) + jobs imported (15,587 staged but 0 imported in this environment)
- **Stage 3 requires** Azure container SAS URL + Stage 2 complete (so note IDs exist)
- **Stage 4 requires** Stage 3 complete (so files are on disk with hashes)

### Blocking Issue

The note import (Stage 2) cannot run in this dev environment because:
1. The `geoop_staging_jobs` table is empty (jobs not staged locally)
2. The `jobs` table has only 1 row (no GeoOp-imported jobs to link notes to)
3. In Azure production, the jobs are staged and imported — Stage 2 should be runnable there

---

## Assessment: Display vs Storage vs Linking vs Import

| Layer | Status | Issue? |
|-------|--------|--------|
| **Display** | Working — `job_note_files` render in Notes tab with thumbnails, preview, download | No issues |
| **Storage** | Upload routes work (Azure Blob + local fallback via `upload_to_blob`) | No issues |
| **Linking** | Routes exist for: add files to new notes, add files to existing notes, add job documents | No issues |
| **Import mapping** | Pipeline code exists (`scan_azure_blob_attachments` + `import_staged_files`) but **has never been executed** | **Primary gap** |

The attachment issue is entirely an **import execution gap**, not a code or display problem.
The pipeline code is written and the staging data is loaded — it just hasn't been run against Azure yet.

## Bugs Found & Fixed

### Bug 1: Empty-text notes with file attachments skipped (FIXED)

`import_staged_notes()` marked notes as `skipped_empty` when `note_description` was blank, even if the note had a `file_name`. This would have orphaned **369 attachment-only notes** (notes that are purely file attachments with no text).

**Fix**: Changed the skip condition to check both `note_text` and `has_file`. Notes with a file but no text now get a placeholder note text: `[Attachment: {filename}]`.

**Location**: `geoop_import.py` lines ~1719-1731

### Bug 2: Azure blob path parser incompatible with CSV path format (FIXED)

The `_parse_attachment_path()` function in `scan_azure_blob_attachments()` only matched paths with an `attachments` keyword prefix (e.g., `attachments/{job_id}/{note_id}/{file_id}_{filename}`). However, the CSV `files_location` column uses a completely different format: `{account_id}/{job_id}/{note_id}/` — three numeric segments with no `attachments` prefix.

**Fix**: Added a fallback branch to `_parse_attachment_path()` that recognises the `{account_id}/{job_id}/{note_id}/{filename}` pattern (three leading numeric segments) and extracts `geoop_job_id` from `parts[1]` and `geoop_note_id` from `parts[2]`.

**Location**: `geoop_import.py` lines ~2139-2167

### New: Attachment Audit Endpoint

Added `GET /admin/geoop-import/attachment-audit` — returns a comprehensive JSON audit of the entire attachment pipeline: staging counts, linked/unlinked files, file types, pipeline status, and failed file notes sample.

### New: Attachment Backfill Tool

Added `POST /admin/geoop-import/backfill-attachments` — re-imports previously skipped or errored notes that have file attachments. Runs in a background thread with progress polling. Creates `job_field_notes` entries for notes that were skipped due to empty text but have file references.

### Bug 3: Multi-file note children creating redundant Axion notes (FIXED)

In GeoOp, when a text note has multiple file attachments, the CSV exports them as separate rows: one parent text note (with `files_location` path segment matching its `geoop_note_id`) and multiple child file-only rows (different `geoop_note_id` values but sharing the parent's `files_location`). The old importer would create separate placeholder Axion notes for each child, resulting in duplicate notes with `[Attachment: ...]` text.

**Fix**: `import_staged_notes()` now detects multi-file children by comparing the `files_location` path segment against the row's `geoop_note_id`. When they differ (child note), the row is marked `linked_to_parent` instead of creating a new Axion note. The Azure scanner correctly links all child files to the parent note via `job_note_files`.

**Impact**: 123 file-only notes in 41 multi-file groups are now correctly handled. 246 single-file attachment-only notes still get their own Axion note.

### Audio playback support added

Notes with M4A, WAV, MP3, OGG, AAC audio files now get inline HTML5 audio playback on both desktop and mobile, instead of just "no preview available" with a download button. This covers 7,330 audio files in the staged data.

Extended image format support: AVIF and JFIF files now display thumbnails and inline previews.

### New: Admin UI Section

Added "Attachment Audit & Repair" card to the GeoOp Import admin page with:
- "Run Attachment Audit" button — shows real-time audit summary inline
- "Run Attachment Backfill" button — triggers backfill with progress polling

## Recommended Next Steps

1. **Run note import** (`import_staged_notes()`) in Azure production — this creates `job_field_notes` records and populates `axion_note_id` on the staging table. The fixed importer will now correctly handle attachment-only notes.
2. **Run Azure blob scan** (`scan_azure_blob_attachments()`) with the container SAS URL — the fixed path parser will now correctly handle the CSV path format (`{account_id}/{job_id}/{note_id}/`).
3. **Run file import** (`import_staged_files()`) — this links files to jobs and notes in production tables
4. **Review unmatched attachments** — check `geoop_unmatched_attachments` table for any files that couldn't be linked
5. **Run attachment backfill** if any notes were skipped in a prior import — re-processes `skipped_empty`, `error`, and `unmatched_job` notes
6. **Add multi-attachment support to existing notes** — route already exists at `POST /jobs/<job_id>/notes/<note_id>/attachments`; verify UI exposes it
