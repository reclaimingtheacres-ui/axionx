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
BACKUP_HOUR = 15
BACKUP_MINUTE = 30
MSG_CLEANUP_HOUR = 16
MSG_CLEANUP_MINUTE = 30
MSG_READ_RETENTION_DAYS = 7

print(f"Backup scheduler started — DB: {DB_PATH} (exists={os.path.exists(DB_PATH)})", flush=True)
print(f"  backup daily at {BACKUP_HOUR:02d}:{BACKUP_MINUTE:02d} UTC (02:30 AEST), msg cleanup at {MSG_CLEANUP_HOUR:02d}:{MSG_CLEANUP_MINUTE:02d} UTC, geocode every 2 min", flush=True)

last_run_date = None
last_geocode_time = 0
last_msg_cleanup_date = None


GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

def _geocode_address(address):
    if not GOOGLE_MAPS_API_KEY:
        return None
    try:
        params = urllib.parse.urlencode({
            "address": address,
            "key": GOOGLE_MAPS_API_KEY,
            "region": "au",
        })
        url = f"https://maps.googleapis.com/maps/api/geocode/json?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if data.get("status") == "OK" and data.get("results"):
            loc = data["results"][0]["geometry"]["location"]
            return float(loc["lat"]), float(loc["lng"])
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
        f" ORDER BY id DESC LIMIT 250",
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
        time.sleep(0.05)

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


def message_cleanup():
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='message_reads'"
        ).fetchall()]
        if 'message_reads' not in tables:
            conn.close()
            return

        cutoff = (datetime.datetime.now() - datetime.timedelta(days=MSG_READ_RETENTION_DAYS)).strftime('%Y-%m-%dT%H:%M:%S')

        system_row = conn.execute(
            "SELECT id FROM users WHERE email='system@axionx.internal'"
        ).fetchone()
        system_uid = system_row[0] if system_row else -1

        stale = conn.execute("""
            SELECT DISTINCT cp.conversation_id, cp.user_id
            FROM conversation_participants cp
            WHERE cp.user_id != ?
              AND NOT EXISTS (
                SELECT 1 FROM conversation_participants cp2
                WHERE cp2.conversation_id = cp.conversation_id AND cp2.user_id = ?
              )
              AND NOT EXISTS (
                SELECT 1 FROM messages m
                WHERE m.conversation_id = cp.conversation_id
                  AND m.is_deleted = 0
                  AND m.sender_id != cp.user_id
                  AND NOT EXISTS (
                      SELECT 1 FROM message_reads mr
                      WHERE mr.message_id = m.id AND mr.user_id = cp.user_id
                  )
            )
            AND EXISTS (
                SELECT 1 FROM messages m2
                WHERE m2.conversation_id = cp.conversation_id AND m2.is_deleted = 0
            )
            AND NOT EXISTS (
                SELECT 1 FROM message_reads mr2
                JOIN messages m3 ON m3.id = mr2.message_id
                WHERE m3.conversation_id = cp.conversation_id
                  AND mr2.user_id = cp.user_id
                  AND mr2.read_at > ?
            )
        """, (system_uid, system_uid, cutoff)).fetchall()

        removed = 0
        for row in stale:
            cid, uid = row["conversation_id"], row["user_id"]
            conn.execute(
                "DELETE FROM conversation_participants WHERE conversation_id=? AND user_id=?",
                (cid, uid)
            )
            conn.execute(
                "DELETE FROM message_reads WHERE user_id=? AND message_id IN (SELECT id FROM messages WHERE conversation_id=?)",
                (uid, cid)
            )
            remaining = conn.execute(
                "SELECT COUNT(*) FROM conversation_participants WHERE conversation_id=?",
                (cid,)
            ).fetchone()[0]
            if remaining == 0:
                conn.execute("DELETE FROM message_reads WHERE message_id IN (SELECT id FROM messages WHERE conversation_id=?)", (cid,))
                conn.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
                conn.execute("DELETE FROM conversations WHERE id=?", (cid,))
            removed += 1

        conn.commit()
        print(f"[{now_str}] Message cleanup: removed {removed} stale read conversation participations (retention={MSG_READ_RETENTION_DAYS}d)", flush=True)
    except Exception:
        print(f"[{now_str}] Message cleanup failed:", flush=True)
        traceback.print_exc()
    finally:
        conn.close()


while True:
    now = datetime.datetime.now()
    today = now.date()

    if now.hour == BACKUP_HOUR and now.minute == BACKUP_MINUTE and last_run_date != today:
        print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Running daily backup...", flush=True)
        try:
            backup()
            last_run_date = today
            print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Backup completed successfully.", flush=True)
        except Exception:
            print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Backup failed:", flush=True)
            traceback.print_exc()

    if now.hour == MSG_CLEANUP_HOUR and now.minute == MSG_CLEANUP_MINUTE and last_msg_cleanup_date != today:
        try:
            message_cleanup()
            last_msg_cleanup_date = today
        except Exception:
            print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Message cleanup failed:", flush=True)
            traceback.print_exc()

    elapsed = time.time() - last_geocode_time
    if elapsed >= 120:
        try:
            geocode_batch()
        except Exception:
            print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Geocode batch failed:", flush=True)
            traceback.print_exc()
        last_geocode_time = time.time()

    time.sleep(60)
