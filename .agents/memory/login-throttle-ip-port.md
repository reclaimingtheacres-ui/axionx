---
name: Login throttle — IP port stripping and permanent lock policy
description: WSGI remote_addr includes source port; locks are permanent (manual release only); successful login does not clear an active lock.
---

# Login throttle — key rules and lock behaviour

## IP port stripping
Always call `_client_ip()` — which calls `_strip_port()` — for the IP used to build throttle keys. Never inline `request.remote_addr` or `X-Forwarded-For` extraction in login routes.

**Why:** Production delivers `remote_addr` with ephemeral source port (e.g. `49.183.137.233:3115`). Each TCP connection is a different key, defeating the threshold.

## Permanent lock policy (as of June 2026)
- Threshold: 3 failed attempts (`_THROTTLE_LIMIT = 3` in `security.py`)
- Lock duration: **permanent** — `locked_until` stores the string `'permanent'` (`_LOCKED_SENTINEL`)
- Auto-release: **disabled** — only Management can release via Settings → Login Security → Release button
- Successful login: `throttle_success()` **skips clearing** if `locked_until` is set — knowing the correct password cannot unlock a locked account

**Why:** Requirement change from timed (10 min) to permanent to prevent brute-force via distributed/slow attacks; aligns with a strict manual-review policy.

**How to apply:** Any new code that calls `throttle_fail()` should use default params (`limit` and `lock_minutes` params removed). `throttle_success()` safely no-ops when a lock is active.
