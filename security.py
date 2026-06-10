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
            key                     TEXT PRIMARY KEY,
            fail_count              INTEGER NOT NULL DEFAULT 0,
            locked_until            TEXT,
            last_attempted_username TEXT,
            updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
            released_by             TEXT,
            released_at             TEXT
        )
    """)
    for col in ("last_attempted_username", "released_by", "released_at"):
        try:
            cur.execute(f"ALTER TABLE login_throttle ADD COLUMN {col} TEXT")
        except Exception:
            pass


def _ensure_audit_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS login_audit_log (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            event_ts            TEXT NOT NULL DEFAULT (datetime('now')),
            event_type          TEXT NOT NULL,
            throttle_key        TEXT,
            ip_address          TEXT,
            username_attempted  TEXT,
            fail_count          INTEGER DEFAULT 0,
            is_locked           INTEGER DEFAULT 0,
            released_by         TEXT,
            released_at         TEXT,
            notes               TEXT
        )
    """)
    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS ix_lal_ts   ON login_audit_log(event_ts DESC)",
        "CREATE INDEX IF NOT EXISTS ix_lal_type ON login_audit_log(event_type)",
        "CREATE INDEX IF NOT EXISTS ix_lal_key  ON login_audit_log(throttle_key)",
    ):
        try:
            cur.execute(idx_sql)
        except Exception:
            pass


def _write_audit(cur, event_type, key, ip_address=None, username=None,
                 fail_count=0, is_locked=False, released_by=None,
                 released_at=None, notes=None):
    _ensure_audit_table(cur)
    cur.execute("""
        INSERT INTO login_audit_log
            (event_ts, event_type, throttle_key, ip_address, username_attempted,
             fail_count, is_locked, released_by, released_at, notes)
        VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_type,
        key or "",
        (ip_address or "").strip(),
        (username or "").lower().strip(),
        int(fail_count),
        1 if is_locked else 0,
        released_by or "",
        released_at or "",
        notes or "",
    ))


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


def throttle_fail(conn, key, username=None, ip=None):
    """Record a failed attempt. Triggers a permanent lockout at _THROTTLE_LIMIT failures.

    Args:
        key:      throttle key — "ip:<addr>" or "user:<email>"
        username: attempted email (stored for audit display; never a password)
        ip:       client IP address — used for audit log when key is a user: key
    """
    cur = conn.cursor()
    _ensure_throttle_table(cur)
    cur.execute("SELECT fail_count, locked_until FROM login_throttle WHERE key=?", (key,))
    row = cur.fetchone()

    already_locked = row and row["locked_until"] == _LOCKED_SENTINEL
    count = (row["fail_count"] if row else 0) + 1
    locked_until = _LOCKED_SENTINEL if (count >= _THROTTLE_LIMIT or already_locked) else None
    newly_locked = (locked_until == _LOCKED_SENTINEL and not already_locked)

    username_val = (username or "").lower().strip()
    ip_address = key[3:] if key.startswith("ip:") else (ip or "")

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
            """INSERT INTO login_throttle
               (key, fail_count, locked_until, last_attempted_username)
               VALUES (?, ?, ?, ?)""",
            (key, count, locked_until, username_val),
        )

    if newly_locked:
        notes = "Account locked after reaching maximum failed attempts."
    elif already_locked:
        notes = "Login attempt while account was locked."
    else:
        notes = None

    _write_audit(cur, "failed_login", key,
                 ip_address=ip_address, username=username_val,
                 fail_count=count, is_locked=bool(locked_until),
                 notes=notes)

    if newly_locked:
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


def throttle_success(conn, key, username=None, ip=None):
    """Record a successful login and clear the failed-attempt counter.

    If an active lockout is in place the counter is NOT cleared — management
    must manually release the lock.  This prevents a locked account from being
    unblocked simply by knowing the correct password.
    """
    cur = conn.cursor()
    _ensure_throttle_table(cur)
    cur.execute("SELECT locked_until FROM login_throttle WHERE key=?", (key,))
    row = cur.fetchone()

    username_val = (username or "").lower().strip()
    ip_address = key[3:] if key.startswith("ip:") else (ip or "")

    _write_audit(cur, "successful_login", key,
                 ip_address=ip_address, username=username_val,
                 fail_count=0, is_locked=False)

    if row and row["locked_until"]:
        # Active lock — leave in place; only management can release.
        return
    cur.execute("DELETE FROM login_throttle WHERE key=?", (key,))


def throttle_clear(conn, key, released_by=None):
    """Management: release a lock.

    Marks the throttle record as released (does NOT delete — history is preserved).
    Writes a lockout_released event to the audit log.
    """
    cur = conn.cursor()
    _ensure_throttle_table(cur)

    cur.execute(
        "SELECT fail_count, last_attempted_username FROM login_throttle WHERE key=?",
        (key,)
    )
    row = cur.fetchone()
    fail_count = row["fail_count"] if row else 0
    username = (row["last_attempted_username"] if row else "") or ""
    ip_address = key[3:] if key.startswith("ip:") else ""

    now_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # Mark as released rather than deleting — preserves history visibility
    cur.execute("""
        UPDATE login_throttle
        SET locked_until = NULL,
            fail_count   = 0,
            released_by  = ?,
            released_at  = datetime('now'),
            updated_at   = datetime('now')
        WHERE key = ?
    """, (released_by or "", key))

    _write_audit(cur, "lockout_released", key,
                 ip_address=ip_address, username=username,
                 fail_count=fail_count, is_locked=False,
                 released_by=released_by,
                 released_at=now_ts,
                 notes=f"Lock released by {released_by or 'admin'}.")