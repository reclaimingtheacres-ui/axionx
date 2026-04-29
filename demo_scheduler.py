#!/usr/bin/env python3
"""
AxionX Demo Auto-Reset Scheduler
==================================
Runs only when AXIONX_DEMO_MODE=true.  Exits immediately in production mode so
it is safe to deploy alongside the main app without any production impact.

At the configured time (default 03:00 AEST, i.e. nightly), it calls
  scripts/seed_demo.py --reset
to wipe and re-seed the demo database, keeping it fresh for new visitors.

Configuration (environment variables):
  AXIONX_DEMO_MODE       — must be "true" for this script to run
  AXIONX_DB_PATH         — path to the demo database
  AXIONX_DEMO_DB_PATH    — alias for AXIONX_DB_PATH (either works)
  AXIONX_DEMO_RESET_CRON — scheduled reset time in "HH:MM" AEST
                            Set to "disabled" or "false" to turn off.
                            Default: "03:00"

Usage (Replit workflow or background process):
  python3 demo_scheduler.py
"""

import os
import sys
import time
import datetime
import subprocess
import traceback
import pytz

# ── Safety: exit immediately in production mode ───────────────────────────────
_DEMO_MODE = os.environ.get("AXIONX_DEMO_MODE", "").lower() in ("1", "true", "yes")
if not _DEMO_MODE:
    print(
        "[demo-scheduler] AXIONX_DEMO_MODE is not set or false — "
        "demo auto-reset scheduler will not run in production. Exiting.",
        flush=True,
    )
    sys.exit(0)

# ── DB path ───────────────────────────────────────────────────────────────────
_DEMO_DB_PATH = os.path.abspath(
    os.environ.get("AXIONX_DEMO_DB_PATH")
    or os.environ.get("AXIONX_DB_PATH")
    or "./axion_demo.db"
)
_PROD_DB_REF = os.path.abspath("axion.db")

# Hard-fail if the demo path resolves to the production DB.
if _DEMO_DB_PATH == _PROD_DB_REF:
    print(
        f"[demo-scheduler] SAFETY: AXIONX_DB_PATH resolves to the production "
        f"database ({_PROD_DB_REF}). Auto-reset scheduler refused to start.",
        file=sys.stderr, flush=True,
    )
    sys.exit(1)

# ── Cron configuration ────────────────────────────────────────────────────────
_CRON_RAW = os.environ.get("AXIONX_DEMO_RESET_CRON", "03:00").strip().lower()
_ENABLED = _CRON_RAW not in ("disabled", "false", "off", "0", "no")
_RESET_HOUR = 3
_RESET_MINUTE = 0

if _ENABLED:
    try:
        parts = _CRON_RAW.split(":")
        _RESET_HOUR = int(parts[0])
        _RESET_MINUTE = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= _RESET_HOUR <= 23 and 0 <= _RESET_MINUTE <= 59):
            raise ValueError("out of range")
    except (ValueError, IndexError):
        print(
            f"[demo-scheduler] AXIONX_DEMO_RESET_CRON={_CRON_RAW!r} is invalid — "
            "falling back to 03:00 AEST.",
            flush=True,
        )
        _RESET_HOUR, _RESET_MINUTE = 3, 0

# ── Timezone ──────────────────────────────────────────────────────────────────
_MELBOURNE = pytz.timezone("Australia/Melbourne")

# ── Startup log ───────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SEED_SCRIPT = os.path.join(_ROOT, "scripts", "seed_demo.py")

print("=" * 64, flush=True)
print("AxionX Demo Auto-Reset Scheduler", flush=True)
print(f"  DB_PATH : {_DEMO_DB_PATH}", flush=True)
if _ENABLED:
    print(f"  Schedule: daily at {_RESET_HOUR:02d}:{_RESET_MINUTE:02d} AEST", flush=True)
else:
    print("  Schedule: DISABLED (AXIONX_DEMO_RESET_CRON=disabled)", flush=True)
print("=" * 64, flush=True)

if not _ENABLED:
    # Nothing to do — park the process so the Replit workflow stays "running".
    print("[demo-scheduler] Scheduler is disabled. Sleeping indefinitely.", flush=True)
    while True:
        time.sleep(3600)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _now_melb() -> datetime.datetime:
    return datetime.datetime.now(_MELBOURNE)


def _run_reset() -> bool:
    """Invoke seed_demo.py --reset.  Returns True on success."""
    now_str = _now_melb().strftime("%Y-%m-%d %H:%M %Z")
    print(f"[{now_str}] Demo auto-reset starting…", flush=True)

    # Re-check safety immediately before writing anything.
    if os.path.abspath(_DEMO_DB_PATH) == _PROD_DB_REF:
        print(
            f"[{now_str}] SAFETY ABORT: DB path resolved to production database. "
            "Reset cancelled.",
            flush=True,
        )
        return False

    env = os.environ.copy()
    env["AXIONX_DEMO_MODE"] = "true"
    env["AXIONX_DEMO_DB_PATH"] = _DEMO_DB_PATH
    env["AXIONX_DB_PATH"] = _DEMO_DB_PATH

    try:
        result = subprocess.run(
            [sys.executable, _SEED_SCRIPT, "--reset"],
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        if result.returncode == 0:
            print(
                f"[{now_str}] Demo auto-reset SUCCESS — DB re-seeded.",
                flush=True,
            )
            return True
        else:
            err = (result.stderr or result.stdout or "unknown error")[:500]
            print(
                f"[{now_str}] Demo auto-reset FAILED (exit {result.returncode}): {err}",
                flush=True,
            )
            return False
    except subprocess.TimeoutExpired:
        print(f"[{now_str}] Demo auto-reset TIMED OUT after 180 s.", flush=True)
        return False
    except Exception:
        print(f"[{now_str}] Demo auto-reset EXCEPTION:", flush=True)
        traceback.print_exc()
        return False


# ── Main loop ─────────────────────────────────────────────────────────────────
_last_reset_date: datetime.date | None = None

while True:
    now = _now_melb()
    today = now.date()

    if (
        now.hour == _RESET_HOUR
        and now.minute == _RESET_MINUTE
        and _last_reset_date != today
    ):
        try:
            success = _run_reset()
            if success:
                _last_reset_date = today
        except Exception:
            print("[demo-scheduler] Unhandled exception in reset loop:", flush=True)
            traceback.print_exc()

    time.sleep(60)
