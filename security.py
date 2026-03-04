from datetime import datetime, timedelta


def _now_utc():
    return datetime.utcnow()


def _parse_dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S") if s else None


def throttle_check(conn, key):
    """
    Returns (allowed: bool, locked_until: str|None).
    Checks whether the given key (e.g. "ip:1.2.3.4") is currently locked out.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT fail_count, locked_until FROM login_throttle WHERE key=?", (key,)
    )
    row = cur.fetchone()

    if row and row["locked_until"]:
        until = _parse_dt(row["locked_until"])
        if until and until > _now_utc():
            return False, row["locked_until"]

    return True, None


def throttle_fail(conn, key, limit=5, lock_minutes=10):
    """Record a failed attempt; lock if limit is reached."""
    cur = conn.cursor()
    cur.execute(
        "SELECT fail_count FROM login_throttle WHERE key=?", (key,)
    )
    row = cur.fetchone()
    count = (row["fail_count"] if row else 0) + 1

    locked_until = None
    if count >= limit:
        locked_until = (
            _now_utc() + timedelta(minutes=lock_minutes)
        ).strftime("%Y-%m-%d %H:%M:%S")

    if row:
        cur.execute(
            """UPDATE login_throttle
               SET fail_count=?, locked_until=?, updated_at=datetime('now')
               WHERE key=?""",
            (count, locked_until, key),
        )
    else:
        cur.execute(
            """INSERT INTO login_throttle (key, fail_count, locked_until)
               VALUES (?, ?, ?)""",
            (key, count, locked_until),
        )


def throttle_success(conn, key):
    """Clear throttle state after a successful login."""
    conn.cursor().execute(
        "DELETE FROM login_throttle WHERE key=?", (key,)
    )
