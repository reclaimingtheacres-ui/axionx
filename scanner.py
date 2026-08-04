"""
scanner.py — Automatic vulnerability scanner detection and temporary IP blocking.

Design principles:
  - In-memory sliding-window counters: zero DB writes per individual probe.
  - DB write only when the block threshold is crossed (rare).
  - In-memory blocked-cache repopulated from DB on startup — O(1) checks per request.
  - Completely separate from manual IP locks (login_throttle / security.py).
  - Thread-safe via a single module-level Lock.

Thresholds (adjustable constants):
  SCANNER_THRESHOLD   = 10 suspicious requests
  SCANNER_WINDOW_SECS = 60 seconds
  SCANNER_BLOCK_HOURS = 24 hours
"""

import re
import time
import ipaddress
import sqlite3
import logging
import threading
import random
from datetime import datetime, timezone

_logger = logging.getLogger("axionx.scanner")
_logger.setLevel(logging.INFO)  # ensure INFO is captured regardless of root logger level

# ── Tunable thresholds ────────────────────────────────────────────────────────
SCANNER_THRESHOLD        = 10     # suspicious hits before block
SCANNER_WINDOW_SECS      = 60     # detection window in seconds
SCANNER_BLOCK_HOURS      = 24     # initial block duration in hours
_AUDIT_UPDATE_INTERVAL   = 300    # update DB record for ongoing probes at most every N sec
_CLEANUP_PROBABILITY     = 0.02   # fraction of hits that trigger in-memory cleanup (1-in-50)

# ── Suspicious path patterns ──────────────────────────────────────────────────
_SUSPICIOUS_PATTERNS = [
    # ── WordPress / PHP probes ─────────────────────────────────────────────
    re.compile(r'\.php',                              re.I),
    re.compile(r'^/wp-admin',                         re.I),
    re.compile(r'^/wp-login',                         re.I),
    re.compile(r'^/wp-content',                       re.I),
    re.compile(r'^/wp-includes',                      re.I),
    re.compile(r'^/xmlrpc\.php',                      re.I),
    re.compile(r'^/cgi-bin',                          re.I),
    re.compile(r'^/phpmyadmin',                       re.I),
    re.compile(r'^/pma(/|$)',                         re.I),
    re.compile(r'shell',                              re.I),
    re.compile(r'c99|r57|b374k|wso|alfa',            re.I),
    re.compile(r'^/backup',                           re.I),

    # ── .env files — any location, any suffix (.env, .env.local, etc.) ───
    re.compile(r'(^|/)\.env($|\.)',                   re.I),

    # ── Terraform / IaC variable files ────────────────────────────────────
    re.compile(r'\.tfvars',                           re.I),

    # ── Sensitive credential / secret filenames ────────────────────────────
    re.compile(r'(credentials|secrets|private)\.(json|ini|yaml|yml|key|pem)', re.I),
    re.compile(r'aws(-config|-credentials)?\.json',   re.I),
    re.compile(r'id_rsa|id_dsa|id_ecdsa',             re.I),
    re.compile(r'\.(pem|p12|pfx|key)$',               re.I),

    # ── Azure Functions / .NET sensitive config files ─────────────────────
    re.compile(r'local\.settings\.json',              re.I),
    re.compile(r'appsettings\.(Development|Staging|Production)\.json', re.I),

    # ── Docker / Fly.io / Heroku / generic DevOps files ───────────────────
    re.compile(r'^/docker-compose\.',                 re.I),
    re.compile(r'^/fly\.toml',                        re.I),
    re.compile(r'^/Procfile($|/)',                    re.I),

    # ── Git / SVN repository exposure ─────────────────────────────────────
    re.compile(r'^/\.git(/|$)',                       re.I),
    re.compile(r'^/\.svn(/|$)',                       re.I),
]

# ── Module state ──────────────────────────────────────────────────────────────
_lock          = threading.Lock()
_db_path       = None

# ip → {count: int, window_start: float, last_path: str, last_ua: str}
_ip_counters: dict = {}

# ip → {until: float, last_audit_at: float, request_count: int}
_blocked_cache: dict = {}

# set of explicitly trusted IPs loaded from DB
_trusted_set: set = set()


# ── Initialisation ────────────────────────────────────────────────────────────

def init(db_path: str):
    """Call once at application startup after the DB schema is ready."""
    global _db_path
    _db_path = db_path
    _load_trusted_ips()
    load_active_blocks_from_db()


# ── Trusted IPs ───────────────────────────────────────────────────────────────

def _load_trusted_ips():
    global _trusted_set
    if not _db_path:
        return
    try:
        conn = sqlite3.connect(_db_path, timeout=5)
        rows = conn.execute(
            "SELECT ip_address FROM scanner_trusted_ips WHERE is_active=1"
        ).fetchall()
        conn.close()
        with _lock:
            _trusted_set = {r[0] for r in rows}
    except Exception:
        pass  # table may not exist yet — handled gracefully


def reload_trusted_ips():
    """Call after an admin adds/removes a trusted IP."""
    _load_trusted_ips()


def _is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return (addr.is_private or addr.is_loopback
                or addr.is_link_local or addr.is_unspecified)
    except ValueError:
        return False


def is_trusted(ip: str) -> bool:
    """Returns True for private/loopback addresses and DB-configured trusted IPs."""
    if _is_private(ip):
        return True
    with _lock:
        return ip in _trusted_set


# ── Suspicious path detection ─────────────────────────────────────────────────

def is_suspicious_path(path: str) -> bool:
    for pattern in _SUSPICIOUS_PATTERNS:
        if pattern.search(path):
            return True
    return False


def get_counter(ip: str) -> int:
    """Return the current suspicious-hit count for ip within the active window (0 if none)."""
    now = time.time()
    with _lock:
        entry = _ip_counters.get(ip)
        if entry is None or (now - entry["window_start"]) > SCANNER_WINDOW_SECS:
            return 0
        return entry["count"]


# ── Block cache ───────────────────────────────────────────────────────────────

def is_blocked(ip: str) -> bool:
    """O(1) in-memory check — no DB hit. Returns True if IP is currently blocked."""
    now = time.time()
    with _lock:
        entry = _blocked_cache.get(ip)
        if entry is None:
            return False
        if now > entry["until"]:
            del _blocked_cache[ip]
            return False
        return True


def load_active_blocks_from_db():
    """Restore active blocks from DB into the in-memory cache at startup."""
    if not _db_path:
        return
    now = time.time()
    try:
        conn = sqlite3.connect(_db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ip_address, blocked_until, request_count "
            "FROM scanner_blocks WHERE is_active=1"
        ).fetchall()
        conn.close()
        with _lock:
            for r in rows:
                try:
                    until_dt = datetime.strptime(
                        r["blocked_until"], "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=timezone.utc)
                    until_ts = until_dt.timestamp()
                    if until_ts > now:
                        _blocked_cache[r["ip_address"]] = {
                            "until":          until_ts,
                            "last_audit_at":  0,
                            "request_count":  r["request_count"] or 0,
                        }
                except Exception:
                    pass
    except Exception:
        pass


# ── Hit recording ─────────────────────────────────────────────────────────────

def record_hit(ip: str, path: str, user_agent: str) -> bool:
    """
    Record one suspicious request from `ip`.

    Returns True  → caller should return the blocked response.
    Returns False → request is within threshold; caller lets it through.

    Only writes to the DB when:
      - The block threshold is first crossed (one INSERT/UPDATE).
      - A blocked IP continues probing after _AUDIT_UPDATE_INTERVAL seconds.
    """
    now = time.time()

    # Probabilistic in-memory cleanup (amortised cost, no background thread needed)
    if random.random() < _CLEANUP_PROBABILITY:
        _cleanup_counters(now)

    should_block     = False
    should_audit     = False
    _already_blocked = False
    block_context    = None   # dict with data needed for the DB write, set outside lock

    with _lock:
        # ── Already blocked? ──────────────────────────────────────────────────
        cached = _blocked_cache.get(ip)
        if cached is not None:
            if now > cached["until"]:
                # Expired — remove and fall through to counter logic below
                del _blocked_cache[ip]
            else:
                # Still blocked — increment probe count and periodically update DB
                cached["request_count"] = cached.get("request_count", 0) + 1
                if (now - cached.get("last_audit_at", 0)) >= _AUDIT_UPDATE_INTERVAL:
                    cached["last_audit_at"] = now
                    should_audit = True
                    block_context = {
                        "kind":          "update",
                        "request_count": cached["request_count"],
                        "last_path":     path,
                        "user_agent":    user_agent,
                    }
                _already_blocked = True

        # Counter logic only runs when IP is not currently blocked.
        # (Expired entries were deleted above, so they fall through correctly.)
        if not _already_blocked:
            # ── Increment window counter ──────────────────────────────────────
            entry = _ip_counters.get(ip)
            if entry is None or (now - entry["window_start"]) > SCANNER_WINDOW_SECS:
                # First hit in a new window — start fresh counter
                _ip_counters[ip] = {
                    "count":        1,
                    "window_start": now,
                    "last_path":    path,
                    "last_ua":      user_agent,
                }
            else:
                entry["count"]    += 1
                entry["last_path"]  = path
                entry["last_ua"]    = user_agent
                count = entry["count"]

                if count >= SCANNER_THRESHOLD:
                    # ── Threshold reached — block ─────────────────────────────
                    blocked_until_ts = now + SCANNER_BLOCK_HOURS * 3600
                    _blocked_cache[ip] = {
                        "until":          blocked_until_ts,
                        "last_audit_at":  now,
                        "request_count":  count,
                    }
                    del _ip_counters[ip]
                    should_block = True
                    block_context = {
                        "kind":             "new",
                        "count":            count,
                        "path":             path,
                        "user_agent":       user_agent,
                        "blocked_until_ts": blocked_until_ts,
                    }

    # ── DB write + logging (outside lock) ────────────────────────────────────
    if should_block and block_context:
        bc = block_context
        _write_block_record(
            ip, bc["path"], bc["user_agent"],
            bc["count"], bc["blocked_until_ts"],
        )
        _logger.warning(
            "SECURITY scanner_block ip=%s count=%d window=%ds duration=%dh",
            ip, bc["count"], SCANNER_WINDOW_SECS, SCANNER_BLOCK_HOURS,
        )

    elif should_audit and block_context:
        bc = block_context
        _update_block_record(ip, bc["last_path"], bc["user_agent"], bc["request_count"])

    return should_block or _already_blocked


# ── DB helpers ────────────────────────────────────────────────────────────────

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _ts_to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _write_block_record(ip: str, path: str, user_agent: str,
                        count: int, blocked_until_ts: float):
    if not _db_path:
        return
    now_iso        = _now_utc_iso()
    blocked_until  = _ts_to_iso(blocked_until_ts)
    reason = (f"Automatic scanner block: {count} suspicious requests "
              f"in {SCANNER_WINDOW_SECS}s")
    try:
        conn = sqlite3.connect(_db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        # Deactivate any old record for this IP before inserting a new one
        conn.execute(
            "UPDATE scanner_blocks SET is_active=0, updated_at=? "
            "WHERE ip_address=? AND is_active=1",
            (now_iso, ip),
        )
        conn.execute("""
            INSERT INTO scanner_blocks
                (ip_address, first_detected_at, last_detected_at,
                 blocked_at, blocked_until, request_count,
                 last_requested_path, reason, user_agent,
                 is_active, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,1,?,?)
        """, (ip, now_iso, now_iso, now_iso, blocked_until,
              count, path, reason, user_agent, now_iso, now_iso))
        conn.commit()
        conn.close()
    except Exception as exc:
        _logger.error(
            "SECURITY scanner_block DB write failed: ip=%s err=%s", ip, exc
        )


def _update_block_record(ip: str, last_path: str, user_agent: str, count: int):
    """Periodic audit update for an IP that keeps probing while blocked."""
    if not _db_path:
        return
    now_iso = _now_utc_iso()
    try:
        conn = sqlite3.connect(_db_path, timeout=10)
        conn.execute("""
            UPDATE scanner_blocks SET
                last_detected_at    = ?,
                last_requested_path = ?,
                user_agent          = ?,
                request_count       = ?,
                updated_at          = ?
            WHERE ip_address=? AND is_active=1
        """, (now_iso, last_path, user_agent, count, now_iso, ip))
        conn.commit()
        conn.close()
    except Exception as exc:
        _logger.error(
            "SECURITY scanner audit update failed: ip=%s err=%s", ip, exc
        )


# ── Admin actions ─────────────────────────────────────────────────────────────

def unblock(ip: str, admin_name: str) -> bool:
    """Clear scanner block for an IP immediately."""
    with _lock:
        _blocked_cache.pop(ip, None)
    if not _db_path:
        return True
    now_iso = _now_utc_iso()
    try:
        conn = sqlite3.connect(_db_path, timeout=10)
        conn.execute("""
            UPDATE scanner_blocks
            SET is_active=0, updated_at=?,
                reason = reason || ' [Unblocked by ' || ? || ' at ' || ? || ']'
            WHERE ip_address=? AND is_active=1
        """, (now_iso, admin_name, now_iso, ip))
        conn.commit()
        conn.close()
        return True
    except Exception as exc:
        _logger.error("SECURITY scanner unblock failed: ip=%s err=%s", ip, exc)
        return False


def extend_block(ip: str, hours: int, admin_name: str) -> bool:
    """Extend the scanner block for an IP by `hours` additional hours."""
    now = time.time()
    now_iso = _now_utc_iso()
    with _lock:
        entry = _blocked_cache.get(ip)
        if entry is not None:
            new_until = max(entry["until"], now) + hours * 3600
            entry["until"] = new_until
        else:
            new_until = now + hours * 3600
            _blocked_cache[ip] = {"until": new_until, "last_audit_at": now, "request_count": 0}
    new_until_iso = _ts_to_iso(new_until)
    if not _db_path:
        return True
    try:
        conn = sqlite3.connect(_db_path, timeout=10)
        rows_updated = conn.execute("""
            UPDATE scanner_blocks
            SET blocked_until=?, updated_at=?,
                reason = reason || ' [Extended +' || ? || 'h by ' || ? || ']',
                is_active = 1
            WHERE ip_address=? AND is_active=1
        """, (new_until_iso, now_iso, str(hours), admin_name, ip)).rowcount
        if rows_updated == 0:
            # No active record — create one
            conn.execute("""
                INSERT INTO scanner_blocks
                    (ip_address, first_detected_at, last_detected_at,
                     blocked_at, blocked_until, request_count,
                     last_requested_path, reason, user_agent,
                     is_active, created_at, updated_at)
                VALUES (?,?,?,?,?,0,'','Manual extension by '||?,'',1,?,?)
            """, (ip, now_iso, now_iso, now_iso, new_until_iso,
                  admin_name, now_iso, now_iso))
        conn.commit()
        conn.close()
        return True
    except Exception as exc:
        _logger.error("SECURITY scanner extend_block failed: ip=%s err=%s", ip, exc)
        return False


def get_all_blocks(active_only: bool = False) -> list:
    """Return scanner block records from the DB."""
    if not _db_path:
        return []
    try:
        conn = sqlite3.connect(_db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        where = "WHERE is_active=1" if active_only else ""
        rows = conn.execute(f"""
            SELECT id, ip_address, first_detected_at, last_detected_at,
                   blocked_at, blocked_until, request_count,
                   last_requested_path, reason, user_agent, is_active,
                   created_at, updated_at
            FROM scanner_blocks
            {where}
            ORDER BY created_at DESC
            LIMIT 500
        """).fetchall()
        conn.close()
        now_iso = _now_utc_iso()
        result = []
        for r in rows:
            status = "inactive"
            if r["is_active"]:
                bu = r["blocked_until"] or ""
                status = "active" if (bu and bu > now_iso) else "expired"
            result.append({
                "id":                 r["id"],
                "ip_address":         r["ip_address"],
                "status":             status,
                "first_detected_at":  r["first_detected_at"] or "",
                "last_detected_at":   r["last_detected_at"] or "",
                "blocked_at":         r["blocked_at"] or "",
                "blocked_until":      r["blocked_until"] or "",
                "request_count":      r["request_count"] or 0,
                "last_requested_path":r["last_requested_path"] or "",
                "reason":             r["reason"] or "",
                "user_agent":         r["user_agent"] or "",
                "is_active":          bool(r["is_active"]),
            })
        return result
    except Exception as exc:
        _logger.error("SECURITY scanner get_all_blocks failed: %s", exc)
        return []


# ── Trusted IP admin ──────────────────────────────────────────────────────────

def get_trusted_ips() -> list:
    if not _db_path:
        return []
    try:
        conn = sqlite3.connect(_db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, ip_address, label, is_active, added_by, created_at, updated_at
            FROM scanner_trusted_ips
            ORDER BY created_at DESC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def add_trusted_ip(ip: str, label: str, added_by: str) -> tuple:
    """
    Add a trusted IP. Returns (ok: bool, error_msg: str | None).
    Reactivates an existing soft-deleted record if found.
    """
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return False, f"Invalid IP address: {ip!r}"

    if not _db_path:
        return False, "DB not initialised"
    now_iso = _now_utc_iso()
    try:
        conn = sqlite3.connect(_db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            "SELECT id, is_active FROM scanner_trusted_ips WHERE ip_address=?", (ip,)
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE scanner_trusted_ips
                SET is_active=1, label=?, added_by=?, updated_at=?
                WHERE ip_address=?
            """, (label, added_by, now_iso, ip))
        else:
            conn.execute("""
                INSERT INTO scanner_trusted_ips
                    (ip_address, label, is_active, added_by, created_at, updated_at)
                VALUES (?,?,1,?,?,?)
            """, (ip, label, added_by, now_iso, now_iso))
        conn.commit()
        conn.close()
        reload_trusted_ips()
        return True, None
    except Exception as exc:
        return False, str(exc)


def remove_trusted_ip(ip: str) -> bool:
    """Soft-delete a trusted IP (set is_active=0)."""
    if not _db_path:
        return False
    now_iso = _now_utc_iso()
    try:
        conn = sqlite3.connect(_db_path, timeout=10)
        conn.execute("""
            UPDATE scanner_trusted_ips SET is_active=0, updated_at=?
            WHERE ip_address=?
        """, (now_iso, ip))
        conn.commit()
        conn.close()
        reload_trusted_ips()
        return True
    except Exception:
        return False


# ── Internal cleanup ──────────────────────────────────────────────────────────

def _cleanup_counters(now: float = None):
    """Remove stale counters and expired block cache entries. Called probabilistically."""
    if now is None:
        now = time.time()
    cutoff = now - SCANNER_WINDOW_SECS
    with _lock:
        stale = [ip for ip, e in _ip_counters.items() if e["window_start"] < cutoff]
        for ip in stale:
            del _ip_counters[ip]
        expired = [ip for ip, e in _blocked_cache.items() if e["until"] < now]
        for ip in expired:
            del _blocked_cache[ip]


def _ensure_scanner_tables(cur):
    """Create scanner DB tables if they don't exist. Used by _startup_migrate."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scanner_blocks (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address           TEXT NOT NULL,
            first_detected_at    TEXT NOT NULL,
            last_detected_at     TEXT NOT NULL,
            blocked_at           TEXT,
            blocked_until        TEXT,
            request_count        INTEGER NOT NULL DEFAULT 0,
            last_requested_path  TEXT,
            reason               TEXT,
            user_agent           TEXT,
            is_active            INTEGER NOT NULL DEFAULT 1,
            created_at           TEXT NOT NULL,
            updated_at           TEXT NOT NULL
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_sb_ip     ON scanner_blocks(ip_address)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_sb_active ON scanner_blocks(is_active, blocked_until)"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scanner_trusted_ips (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address  TEXT NOT NULL UNIQUE,
            label       TEXT,
            is_active   INTEGER NOT NULL DEFAULT 1,
            added_by    TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_sti_ip ON scanner_trusted_ips(ip_address)"
    )
