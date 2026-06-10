import logging as _log
from datetime import datetime, timedelta

_logger = _log.getLogger("axionx.security")


def _now_utc():
    return datetime.utcnow()


def _parse_dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S") if s else None


def _ensure_throttle_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS login_throttle (
            key TEXT PRIMARY KEY,
            fail_count INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            last_attempted_username TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    try:
        cur.execute("ALTER TABLE login_throttle ADD COLUMN last_attempted_username TEXT")
    except Exception:
        pass


def throttle_check(conn, key):
    """
    Returns (allowed: bool, locked_until: str|None).
    Checks whether the given key (e.g. "ip:1.2.3.4" or "user:email@x.com") is currently locked.
    """
    cur = conn.cursor()
    _ensure_throttle_table(cur)
    cur.execute(
        "SELECT fail_count, locked_until FROM login_throttle WHERE key=?", (key,)
    )
    row = cur.fetchone()

    if row and row["locked_until"]:
        until = _parse_dt(row["locked_until"])
        if until and until > _now_utc():
            return False, row["locked_until"]

    return True, None


def throttle_fail(conn, key, limit=5, lock_minutes=10, username=None):
    """Record a failed attempt; lock if limit is reached.

    Args:
        key: throttle key — either "ip:<addr>" or "user:<email>"
        username: the attempted login username/email (stored for audit; never a password)
    """
    cur = conn.cursor()
    _ensure_throttle_table(cur)
    cur.execute("SELECT fail_count FROM login_throttle WHERE key=?", (key,))
    row = cur.fetchone()
    count = (row["fail_count"] if row else 0) + 1

    locked_until = None
    if count >= limit:
        locked_until = (
            _now_utc() + timedelta(minutes=lock_minutes)
        ).strftime("%Y-%m-%d %H:%M:%S")

    username_val = (username or "").lower().strip()

    if row:
        cur.execute(
            """UPDATE login_throttle
               SET fail_count=?, locked_until=?, last_attempted_username=?,
                   updated_at=datetime('now')
               WHERE key=?""",
            (count, locked_until, username_val, key),
        )
    else:
        cur.execute(
            """INSERT INTO login_throttle (key, fail_count, locked_until, last_attempted_username)
               VALUES (?, ?, ?, ?)""",
            (key, count, locked_until, username_val),
        )

    if locked_until:
        _logger.warning(
            "[LOGIN LOCKOUT] key=%r locked until %s UTC — fail_count=%d last_username=%r",
            key, locked_until, count, username_val,
        )
    else:
        _logger.warning(
            "[LOGIN FAIL] key=%r fail_count=%d last_username=%r",
            key, count, username_val,
        )


def throttle_success(conn, key):
    """Clear throttle state after a successful login."""
    conn.cursor().execute(
        "DELETE FROM login_throttle WHERE key=?", (key,)
    )


def throttle_clear(conn, key):
    """Admin: manually clear a specific throttle entry."""
    conn.cursor().execute(
        "DELETE FROM login_throttle WHERE key=?", (key,)
    )
