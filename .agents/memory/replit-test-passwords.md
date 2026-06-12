---
name: Replit test DB passwords
description: Known passwords for test accounts in axion.db (Replit workspace only) — do not change these without the user's knowledge and restoring afterwards.
---

## Rule
Never change real user account passwords in `axion.db` for testing purposes. If a password must be changed to test something, restore it immediately and tell the user.

**Why:** A prior session set `management@axion.local` to `test123` for testing and did not restore it. The user could not log in because their real password (`Manage2024!`) stopped working. This caused a complete lockout and eroded trust.

## Known Replit test account passwords (as of June 2026)

| Email | Password | Role |
|---|---|---|
| management@axion.local | Manage2024! | management |
| admin@axion.local | Manage2024! | admin |

The remaining accounts (danielc@, grantc@, updates@swpirecoveries.com) have unknown passwords — do not guess or reset them.

## How to apply
- Before any test that requires logging in, verify you know the current password rather than changing it.
- If the login throttle locks an account: `DELETE FROM login_throttle` in `axion.db` — do NOT reset the password as part of the unlock.
- If a password must be changed for a test, document the original hash first and restore it in the same session.
