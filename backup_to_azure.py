import datetime
import gzip
import os
import sqlite3
import glob

DB_PATH = os.environ.get("DB_PATH", "axion.db")
BACKUP_DIR = os.path.dirname(os.path.abspath(DB_PATH)) or "."
CONTAINER = "axionx-backups"
RETENTION_DAYS = 30
LOCAL_KEEP = 7


def _sqlite_backup(src_path, dst_path):
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
        dst.execute("PRAGMA integrity_check")
    finally:
        dst.close()
        src.close()


def _rotate_local(backup_dir, keep=LOCAL_KEEP):
    pattern = os.path.join(backup_dir, "axion_backup_*.db")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    for old in files[keep:]:
        try:
            os.remove(old)
            print(f"Rotated local backup: {old}")
        except OSError as e:
            print(f"Could not remove {old}: {e}")


def backup():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")

    local_backup = os.path.join(BACKUP_DIR, f"axion_backup_{timestamp}.db")
    print(f"SQLite backup {DB_PATH} -> {local_backup} ...", flush=True)
    _sqlite_backup(DB_PATH, local_backup)
    print(f"Local backup written: {local_backup} ({os.path.getsize(local_backup)} bytes)", flush=True)

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
            print(f"Azure backup uploaded: {blob_name}", flush=True)
            _cleanup_azure(container)
        except Exception as e:
            print(f"Azure upload failed (local backup is safe): {e}", flush=True)
    else:
        print("AZURE_STORAGE_CONNECTION_STRING not set — skipping Azure upload.", flush=True)


def _cleanup_azure(container):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=RETENTION_DAYS)
    for blob in container.list_blobs():
        if blob.last_modified.replace(tzinfo=datetime.timezone.utc) < cutoff:
            container.delete_blob(blob.name)
            print(f"Deleted old Azure backup: {blob.name}")


if __name__ == "__main__":
    backup()
