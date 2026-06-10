---
name: Login throttle IP port stripping
description: WSGI remote_addr includes source port (e.g. 49.183.137.233:3115); throttle keys must strip it.
---

# Login throttle IP port stripping

## The rule
Always call `_strip_port()` on any IP used to build a `login_throttle` key. Use `_client_ip()` — which already calls `_strip_port()` — rather than inlining `request.remote_addr` or `X-Forwarded-For` extraction.

**Why:** Production (Azure/gunicorn behind proxy) delivers `remote_addr` with the source port attached. Each TCP connection from the same client gets a different ephemeral port, so without stripping, every failed attempt is recorded under a unique key and the lockout threshold is never reached.

**How to apply:** Both `/login` POST and `/m/login` POST routes must use `ip = _client_ip()`. Any future login-adjacent route that reads the client IP for throttling should do the same.
