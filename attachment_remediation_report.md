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

## Recommended Next Steps

1. **Run note import** (`import_staged_notes()`) in Azure production — this creates `job_field_notes` records and populates `axion_note_id` on the staging table
2. **Run Azure blob scan** (`scan_azure_blob_attachments()`) with the container SAS URL — this fetches 58,909 files and populates `geoop_staging_files`
3. **Run file import** (`import_staged_files()`) — this links files to jobs and notes in production tables
4. **Review unmatched attachments** — check `geoop_unmatched_attachments` table for any files that couldn't be linked
5. **Add multi-attachment support to existing notes** — route already exists at `POST /jobs/<job_id>/notes/<note_id>/attachments`; verify UI exposes it
