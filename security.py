import logging as _log
from datetime import datetime

_logger = _log.getLogger("axionx.security")

# Lockout is triggered after this many failed attempts.
_THROTTLE_LIMIT = 3

# Sentinel stored in locked_until for indefinite (management-release-only) locks.
_LOCKED_SENTINEL = "permanent"


def _now_utc():
    return datetime.utcnow()


def _parse_dt(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


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
    """Return (allowed: bool, lock_status: str|None).

    lock_status is None when allowed, 'permanent' for an indefinite lock,
    or a datetime string for a time-based lock (legacy rows).
    """
    cur = conn.cursor()
    _ensure_throttle_table(cur)
    cur.execute(
        "SELECT fail_count, locked_until FROM login_throttle WHERE key=?", (key,)
    )
    row = cur.fetchone()

    if row and row["locked_until"]:
        lu = row["locked_until"]
        if lu == _LOCKED_SENTINEL:
            return False, _LOCKED_SENTINEL
        # Legacy: time-based lock (may exist from older rows in production)
        until = _parse_dt(lu)
        if until and until > _now_utc():
            return False, lu

    return True, None


def throttle_fail(conn, key, username=None):
    """Record a failed attempt.  Triggers a permanent lockout at _THROTTLE_LIMIT failures.

    Args:
        key:      throttle key — "ip:<addr>" or "user:<email>"
        username: attempted email (stored for audit display; never a password)
    """
    cur = conn.cursor()
    _ensure_throttle_table(cur)
    cur.execute("SELECT fail_count, locked_until FROM login_throttle WHERE key=?", (key,))
    row = cur.fetchone()

    # If already permanently locked, just bump the counter (don't downgrade the lock).
    already_locked = row and row["locked_until"] == _LOCKED_SENTINEL
    count = (row["fail_count"] if row else 0) + 1

    locked_until = _LOCKED_SENTINEL if (count >= _THROTTLE_LIMIT or already_locked) else None

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

    if locked_until == _LOCKED_SENTINEL and not already_locked:
        _logger.warning(
            "[LOGIN LOCKOUT] key=%r PERMANENTLY LOCKED — fail_count=%d last_username=%r",
            key, count, username_val,
        )
    elif locked_until == _LOCKED_SENTINEL:
        _logger.warning(
            "[LOGIN BLOCKED-ATTEMPT] key=%r still locked — fail_count=%d last_username=%r",
            key, count, username_val,
        )
    else:
        _logger.warning(
            "[LOGIN FAIL] key=%r fail_count=%d/%d last_username=%r",
            key, count, _THROTTLE_LIMIT, username_val,
        )


def throttle_success(conn, key):
    """Clear failed-attempt counter after a successful login.

    If an active lockout is in place the counter is NOT cleared — management
    must manually release the lock.  This prevents a locked account from being
    unblocked simply by knowing the correct password.
    """
    cur = conn.cursor()
    _ensure_throttle_table(cur)
    cur.execute("SELECT locked_until FROM login_throttle WHERE key=?", (key,))
    row = cur.fetchone()
    if row and row["locked_until"]:
        # Active lock — leave in place; only management can release.
        return
    cur.execute("DELETE FROM login_throttle WHERE key=?", (key,))


def throttle_clear(conn, key):
    """Management: manually release a lock and clear the failed-attempt record."""
    conn.cursor().execute(
        "DELETE FROM login_throttle WHERE key=?", (key,)
    )
