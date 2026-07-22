import datetime
import gzip
import os
import sqlite3
import glob

DB_PATH = os.environ.get("DB_PATH", "axion.db")
BACKUP_DIR = os.path.dirname(os.path.abspath(DB_PATH)) or "."
CONTAINER = "axionx-backups"
RETENTION_DAYS = 30
LOCAL_KEEP = int(os.environ.get("AXIONX_LOCAL_BACKUP_RETENTION", "3"))


def _sqlite_backup(src_path, dst_path):
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
        dst.execute("PRAGMA integrity_check")
    finally:
        dst.close()
        src.close()


def _rotate_local(backup_dir, keep=None):
    if keep is None:
        keep = int(os.environ.get("AXIONX_LOCAL_BACKUP_RETENTION", str(LOCAL_KEEP)))
    pattern = os.path.join(backup_dir, "axion_backup_*.db")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    retained = files[:keep]
    to_delete = files[keep:]
    for f in retained:
        print(f"[backup-rotate] Retained: {f}", flush=True)
    for old in to_delete:
        try:
            os.remove(old)
            print(f"[backup-rotate] Deleted: {old}", flush=True)
        except OSError as e:
            print(f"[backup-rotate] Could not delete {old}: {e}", flush=True)


def backup_exists_today(backup_dir=None):
    """Return True if a local backup file for today already exists."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    d = backup_dir or BACKUP_DIR
    return bool(glob.glob(os.path.join(d, f"axion_backup_{today}_*.db")))


def backup():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")

    local_backup = os.path.join(BACKUP_DIR, f"axion_backup_{timestamp}.db")
    print(f"LOCAL BACKUP START: {DB_PATH} -> {local_backup}", flush=True)
    _sqlite_backup(DB_PATH, local_backup)
    size = os.path.getsize(local_backup)
    print(f"LOCAL BACKUP SUCCESS: {local_backup} ({size:,} bytes)", flush=True)

    _rotate_local(BACKUP_DIR)

    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        try:
            from azure.storage.blob import BlobServiceClient
            blob_name = f"axion_{timestamp}.db.gz"
            with open(local_backup, "rb") as f:
                compressed = gzip.compress(f.read())
            blob_service = BlobServiceClient.from_connection_string(conn_str)
            container = blob_service.get_container_client(CONTAINER)
            container.upload_blob(name=blob_name, data=compressed, overwrite=True)
            print(f"AZURE UPLOAD SUCCESS: {blob_name}", flush=True)
            _cleanup_azure(container)
        except Exception as e:
            print(f"AZURE UPLOAD FAILED (local backup retained): {e}", flush=True)
    else:
        print("AZURE_STORAGE_CONNECTION_STRING not set — skipping Azure upload.", flush=True)


def _cleanup_azure(container):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=RETENTION_DAYS)
    for blob in container.list_blobs():
        if blob.last_modified.replace(tzinfo=datetime.timezone.utc) < cutoff:
            container.delete_blob(blob.name)
            print(f"Deleted old Azure backup: {blob.name}", flush=True)


if __name__ == "__main__":
    backup()
