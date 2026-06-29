---
phase: 02
plan: 02
subsystem: authorization-foundation
tags: [authz, api, homepage, security, tests]
key-files:
  - pickem/pickem_api/permissions.py
  - pickem/pickem_api/views.py
  - pickem/pickem_api/urls.py
  - pickem/pickem_homepage/authz.py
  - pickem/pickem_api/tests.py
  - pickem/pickem_homepage/tests.py
metrics:
  api-tests: "47 pickem_api tests passed"
  homepage-tests: "45 pickem_homepage tests passed"
---

# Phase 02 Plan 02 Summary: View/API Guards And Proof Integration

## What Changed

Added browser and API adapters around the shared tenant authorization helpers.

Browser/page support:

- Added `pickem_homepage.authz.family_member_required`.
- The decorator attaches `request.tenant_context` for authorized requests.
- Anonymous browser requests redirect to login.
- Authenticated non-members raise 404.
- Active members with insufficient role receive 403.

API support:

- Added `tenant_authz_error_response()` to map shared helper denials to JSON responses.
- Added `GET /api/families/<family_slug>/pools/<pool_slug>/authz-check/` as a minimal Phase 2 proof endpoint.
- The proof endpoint returns only family slug, pool slug, and active membership role for authorized users.

## Commits

| Commit | Description |
|--------|-------------|
| `acffd7b` | `feat(02-02): add tenant guard adapters` |

## Verification

Commands run:

```bash
cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings
cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings
```

Results:

- 47 `pickem_api` tests passed.
- 45 `pickem_homepage` tests passed.
- Existing warnings remain for `max_length` on `IntegerField` fields in `userStats`.

## Deviations from Plan

None - plan executed exactly as written.

## Security Notes

- The API proof route uses `AllowAny` intentionally so the shared helper controls anonymous handling and returns a consistent auth error.
- Non-member API responses are generic `404` with `Not found.`
- Role denial responses are generic `403` with `Permission denied.`
- The proof route does not migrate any product pages or expose picks, standings, members, settings, invitations, or dashboard data.

## Self-Check: PASSED

- Browser adapter behavior is tested.
- API adapter behavior is tested.
- Cross-family and pool-family mismatch denial paths are tested.
- Existing homepage focused tests still pass.
