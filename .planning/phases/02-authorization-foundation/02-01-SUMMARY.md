---
phase: 02
plan: 01
subsystem: authorization-foundation
tags: [authz, tenancy, security, tests]
key-files:
  - pickem/pickem_api/authz.py
  - pickem/pickem_api/tests.py
metrics:
  tests: "41 pickem_api tests passed"
---

# Phase 02 Plan 01 Summary: Core Tenant Authorization Helpers

## What Changed

Added `pickem_api.authz` as the centralized family/pool authorization helper module.

The module now provides:

- tenant denial classes for authentication-required, tenant-not-found, and tenant-permission-denied outcomes;
- role ordering for `member`, `admin`, and `owner`;
- active family membership checks;
- pool resolution with family consistency checks;
- no implicit superuser or legacy commissioner bypass;
- explicit opt-in legacy default pool fallback;
- active membership listing for later onboarding/switcher work.

Added focused helper tests covering active members, role ladder behavior, inactive memberships, outsiders, anonymous users, superusers, legacy commissioners, cross-family pool denial, pool-family mismatch, and explicit legacy fallback.

## Commits

| Commit | Description |
|--------|-------------|
| `4425ca8` | `feat(02-01): add tenant authorization helpers` |

## Verification

Command run:

```bash
cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings
```

Result:

- 41 tests passed.
- Existing warnings remain for `max_length` on `IntegerField` fields in `userStats`.

## Deviations from Plan

None - plan executed exactly as written.

## Security Notes

- Superusers and `UserProfile.is_commissioner=True` users are denied tenant helper access unless they also have explicit active `FamilyMembership`.
- Inactive memberships are treated as not found.
- Pool access validates that supplied pool context belongs to the supplied family.
- Legacy default pool fallback requires `allow_legacy_default=True`.

## Self-Check: PASSED

- Core helper module exists.
- Negative authorization tests exist and pass.
- No database migration was added.
