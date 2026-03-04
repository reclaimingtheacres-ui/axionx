import datetime
import gzip
import os
from azure.storage.blob import BlobServiceClient

DB_FILE = "axionx.db"
CONTAINER = "axionx-backups"

def backup():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    backup_file = f"axionx_{timestamp}.db.gz"

    with open(DB_FILE, "rb") as f:
        data = f.read()

    compressed = gzip.compress(data)

    conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    blob_service = BlobServiceClient.from_connection_string(conn_str)

    container = blob_service.get_container_client(CONTAINER)

    container.upload_blob(
        name=backup_file,
        data=compressed,
        overwrite=True
    )

    print("Backup uploaded:", backup_file)

backup()
