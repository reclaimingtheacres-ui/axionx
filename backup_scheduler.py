import time
import datetime
import traceback
import os
import sqlite3
import urllib.request
import urllib.parse
import json

from backup_to_azure import backup

DB_PATH = os.path.abspath(os.environ.get("DB_PATH", "axion.db"))
ARCHIVED_STATUSES = ("Archived - Invoiced", "Cold Stored")
EXCLUDED_STATUSES = ('Closed', 'Cancelled') + ARCHIVED_STATUSES

print(f"Backup scheduler started — DB: {DB_PATH} (exists={os.path.exists(DB_PATH)})", flush=True)
print("  backup daily at 02:00, geocode every 10 min", flush=True)

last_run_date = None
last_geocode_time = 0


def _geocode_address(address):
    try:
        params = urllib.parse.urlencode({
            "q": address,
            "format": "json",
            "limit": 1,
            "countrycodes": "au",
        })
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AxionX/1.0 field-ops (contact@swpirecoveries.com.au)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


def geocode_batch():
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ph = ','.join('?' for _ in EXCLUDED_STATUSES)
    pending = conn.execute(
        f"SELECT id, job_address FROM jobs"
        f" WHERE job_address IS NOT NULL AND job_address != ''"
        f"   AND (lat IS NULL OR lng IS NULL)"
        f"   AND status NOT IN ({ph})"
        f"   AND (geocode_fail IS NULL OR geocode_fail < 3)"
        f" ORDER BY id DESC LIMIT 30",
        EXCLUDED_STATUSES
    ).fetchall()

    if not pending:
        conn.close()
        return

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"[{now}] Geocoding {len(pending)} jobs...", flush=True)
    updated = 0
    failed = 0
    for job in pending:
        result = _geocode_address(job["job_address"])
        if result:
            lat, lng = result
            try:
                conn.execute("UPDATE jobs SET lat=?, lng=? WHERE id=?",
                             (lat, lng, job["id"]))
                conn.commit()
                updated += 1
            except Exception:
                pass
        else:
            try:
                conn.execute(
                    "UPDATE jobs SET geocode_fail = COALESCE(geocode_fail,0)+1 WHERE id=?",
                    (job["id"],))
                conn.commit()
                failed += 1
            except Exception:
                pass
        time.sleep(1.1)

    remaining = conn.execute(
        f"SELECT COUNT(*) FROM jobs"
        f" WHERE job_address IS NOT NULL AND job_address != ''"
        f"   AND (lat IS NULL OR lng IS NULL)"
        f"   AND status NOT IN ({ph})"
        f"   AND (geocode_fail IS NULL OR geocode_fail < 3)",
        EXCLUDED_STATUSES
    ).fetchone()[0]
    conn.close()
    now2 = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"[{now2}] Geocode batch done: {updated} updated, {failed} failed, {remaining} remaining", flush=True)


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

    elapsed = time.time() - last_geocode_time
    if elapsed >= 600:
        try:
            geocode_batch()
        except Exception:
            print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Geocode batch failed:", flush=True)
            traceback.print_exc()
        last_geocode_time = time.time()

    time.sleep(60)
