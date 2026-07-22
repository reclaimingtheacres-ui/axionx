import datetime
import fcntl
import gzip
import glob
import os
import shutil
import sqlite3
import tempfile

DB_PATH    = os.environ.get("DB_PATH", "axion.db")
BACKUP_DIR = os.path.dirname(os.path.abspath(DB_PATH)) or "."
CONTAINER  = "axionx-backups"

# Configurable via environment — defaults match historical behaviour.
LOCAL_KEEP     = int(os.environ.get("AXIONX_LOCAL_BACKUP_RETENTION", "3"))
RETENTION_DAYS = int(os.environ.get("AXIONX_AZURE_RETENTION_DAYS",   "30"))

# A single lock file shared by every process that imports this module
# (backup_scheduler.py and the app watchdog thread live in different
# processes but share the same filesystem on Azure App Service).
_LOCK_PATH = os.path.join(BACKUP_DIR, ".axionx_backup.lock")


# ── Cross-process exclusive lock ──────────────────────────────────────────────

def _acquire_backup_lock():
    """Acquire an exclusive advisory file lock (non-blocking).

    Returns the open lock file handle on success.
    Raises RuntimeError immediately if another process/thread already holds it,
    so the caller can log and skip rather than block.

    fcntl.flock locks are automatically released when the file descriptor is
    garbage-collected or the owning process exits — no stale-lock risk on crash.
    """
    lf = open(_LOCK_PATH, "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lf.close()
        raise RuntimeError(
            "Another backup is already running — skipping duplicate trigger."
        )
    return lf


def _release_backup_lock(lf):
    try:
        fcntl.flock(lf, fcntl.LOCK_UN)
        lf.close()
    except Exception:
        pass


# ── Core SQLite copy ───────────────────────────────────────────────────────────

def _sqlite_backup(src_path, dst_path):
    """Copy src_path → dst_path using SQLite's online backup API.

    Raises RuntimeError if the destination copy fails integrity_check.
    The caller is responsible for deleting dst_path on failure.
    """
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
        row = dst.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise RuntimeError(
                f"Integrity check failed on backup copy: "
                f"{row[0] if row else 'no result'}"
            )
    finally:
        dst.close()
        src.close()


# ── Local rotation ─────────────────────────────────────────────────────────────

def _rotate_local(backup_dir, keep=None):
    """Keep the <keep> most-recent axion_backup_*.db files; delete the rest.

    Only called after a new backup has passed integrity validation.
    Sorts by actual file modification time, not filename.
    Never touches WAL/SHM files, the live database, or any other file type.
    """
    if keep is None:
        keep = int(os.environ.get("AXIONX_LOCAL_BACKUP_RETENTION", str(LOCAL_KEEP)))
    pattern = os.path.join(backup_dir, "axion_backup_*.db")
    files   = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    for f in files[:keep]:
        print(f"[backup-rotate] Retained: {f}", flush=True)
    for old in files[keep:]:
        try:
            os.remove(old)
            print(f"[backup-rotate] Deleted:  {old}", flush=True)
        except OSError as e:
            print(f"[backup-rotate] Could not delete {old}: {e}", flush=True)


# ── Today-check (used by both scheduler and watchdog) ─────────────────────────

def backup_exists_today(backup_dir=None):
    """Return True if a local backup file for today already exists."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    d = backup_dir or BACKUP_DIR
    return bool(glob.glob(os.path.join(d, f"axion_backup_{today}_*.db")))


# ── Public entry point ─────────────────────────────────────────────────────────

def backup():
    """Run a full backup cycle with cross-process exclusion.

    Raises RuntimeError if a backup is already in progress (caller should log
    and skip, not treat as a hard error).  All other exceptions indicate a
    genuine backup failure and propagate normally.
    """
    lf = _acquire_backup_lock()
    try:
        _backup_inner()
    finally:
        _release_backup_lock(lf)


def _backup_inner():
    timestamp    = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    local_backup = os.path.join(BACKUP_DIR, f"axion_backup_{timestamp}.db")

    print(f"LOCAL BACKUP START: {DB_PATH} -> {local_backup}", flush=True)

    try:
        _sqlite_backup(DB_PATH, local_backup)
    except Exception:
        # Remove a partial/corrupt backup file so it is not mistaken for a
        # valid copy and does not consume a rotation slot.
        try:
            if os.path.exists(local_backup):
                os.remove(local_backup)
        except OSError:
            pass
        raise

    size = os.path.getsize(local_backup)
    print(f"LOCAL BACKUP SUCCESS: {local_backup} ({size:,} bytes)", flush=True)

    # Rotation only runs after the new backup has passed integrity validation.
    _rotate_local(BACKUP_DIR)

    _upload_to_azure(local_backup, timestamp)


def _upload_to_azure(local_backup, timestamp):
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        print("AZURE_STORAGE_CONNECTION_STRING not set — skipping Azure upload.", flush=True)
        return

    try:
        from azure.storage.blob import BlobServiceClient

        blob_name    = f"axion_{timestamp}.db.gz"
        blob_service = BlobServiceClient.from_connection_string(conn_str)
        container    = blob_service.get_container_client(CONTAINER)

        # Stream-compress to a temp file so the full database is never held
        # in memory.  On Azure the live DB is ~290 MB; in-memory compression
        # would double peak RSS for the duration of the backup.
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db.gz", dir=BACKUP_DIR)
        try:
            os.close(tmp_fd)
            with open(local_backup, "rb") as src_f, \
                 gzip.open(tmp_path, "wb") as gz_f:
                shutil.copyfileobj(src_f, gz_f)

            with open(tmp_path, "rb") as upload_f:
                container.upload_blob(name=blob_name, data=upload_f, overwrite=True)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        print(f"AZURE UPLOAD SUCCESS: {blob_name}", flush=True)
        _cleanup_azure(container)

    except Exception as e:
        print(f"AZURE UPLOAD FAILED (local backup retained): {e}", flush=True)


def _cleanup_azure(container):
    """Delete AxionX backup blobs older than the retention window.

    Only deletes blobs whose name matches the pattern axion_*.db.gz so that
    any non-backup objects sharing the container are never touched.
    Re-reads AXIONX_AZURE_RETENTION_DAYS at call time so the value can be
    changed via env var without a process restart.
    """
    retention = int(os.environ.get("AXIONX_AZURE_RETENTION_DAYS", str(RETENTION_DAYS)))
    cutoff    = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention)
    for blob in container.list_blobs():
        if not (blob.name.startswith("axion_") and blob.name.endswith(".db.gz")):
            continue
        if blob.last_modified.replace(tzinfo=datetime.timezone.utc) < cutoff:
            container.delete_blob(blob.name)
            print(f"Deleted old Azure backup: {blob.name}", flush=True)


if __name__ == "__main__":
    backup()
