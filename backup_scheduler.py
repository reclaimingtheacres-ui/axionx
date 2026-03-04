import time
import datetime
import traceback
from backup_to_azure import backup

print("Backup scheduler started — will run backup daily at 02:00", flush=True)

last_run_date = None

while True:
    now = datetime.datetime.now()
    today = now.date()

    if now.hour == 2 and now.minute == 0 and last_run_date != today:
        print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Running daily backup...", flush=True)
        try:
            backup()
            last_run_date = today
            print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Backup completed successfully.", flush=True)
        except Exception:
            print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Backup failed:", flush=True)
            traceback.print_exc()

    time.sleep(60)
