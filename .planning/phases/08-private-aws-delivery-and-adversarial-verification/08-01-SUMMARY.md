---
phase: 08-private-aws-delivery-and-adversarial-verification
plan: 01
subsystem: storage-security
tags: [django, s3, django-storages, signed-urls, csrf, transactions]
requires:
  - phase: 06-secure-logo-foundation
    provides: Canonical WebP family-logo generation and tenant-authorized storage writes.
  - phase: 07-commissioner-upload-and-delivery-experience
    provides: Commissioner settings upload/replacement/removal workflow.
provides:
  - Dedicated FAMILY_LOGO_* S3 configuration that cannot inherit generic AWS credentials.
  - Fixed five-minute private signed logo URLs with local-media fallback only for entirely absent logo configuration.
  - Post-commit deletion of precisely the superseded generated logo object.
  - Route-level hostile-request and persistence-failure regression coverage.
affects: [08-02, 08-03, release, aws]
tech-stack:
  added: []
  patterns: [logo-only credentials, post-commit obsolete-object cleanup, fail-closed storage configuration]
key-files:
  created: []
  modified:
    - pickem/pickem/settings.py
    - pickem/pickem_api/storage.py
    - pickem/pickem_api/tests/test_family_logo_storage.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/tests.py
key-decisions:
  - "FamilyLogoStorage reads only dedicated FAMILY_LOGO_* settings and requires all credential fields together."
  - "Old generated objects are deleted via transaction.on_commit only after the row and audit record succeed."
patterns-established:
  - "Post-commit cleanup: capture the old server-generated name before mutation, then bind it into an on-commit callback."
  - "S3 configuration: missing all dedicated values means local development storage; any partial set is an error."
requirements-completed: [S3-02, SAFE-02, SAFE-03]
coverage:
  - id: D1
    description: Dedicated family-logo S3 credentials and bounded private signed URLs.
    requirement: S3-02
    verification:
      - kind: unit
        ref: pickem_api.tests.test_family_logo_storage.FamilyLogoStorageTests
        status: pass
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=1"
        status: pass
    human_judgment: false
  - id: D2
    description: Tenant/CSRF hostile mutations and object lifecycle compensation remain side-effect free or delete only obsolete keys.
    requirement: SAFE-02
    verification:
      - kind: integration
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests
        status: pass
    human_judgment: false
  - id: D3
    description: Committed replacement/removal cleans the exact obsolete generated key after audit success.
    requirement: SAFE-03
    verification:
      - kind: integration
        ref: pickem_homepage.tests.FamilyLogoUploadFoundationTests
        status: pass
    human_judgment: false
duration: 24min
completed: 2026-07-19
status: complete
---

# Phase 8 Plan 1: Private Logo Runtime Summary

**Dedicated logo-only S3 credentials, five-minute signed delivery, and transaction-safe cleanup protect the existing commissioner upload workflow.**

## Performance

- **Duration:** 24 min
- **Completed:** 2026-07-19
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added all-or-none `FAMILY_LOGO_*` configuration and validated five-minute signing expiry without changing static-file or backup credentials.
- Made `FamilyLogoStorage` use only the dedicated logo credentials; development remains local only when every logo setting is absent.
- Added post-commit stale-object cleanup for replacement and removal while retaining pre-commit compensation for failed writes/audits.
- Proved lifecycle, forged route/body, member/outsider/anonymous, and CSRF rejection paths with isolated Django tests.

## Task Commits

1. **Task 1: Bind FamilyLogoStorage to dedicated logo-only configuration** - `8c17acc` (feat)
2. **Task 2: Clean obsolete objects only after successful locked mutations** - `086b702` (fix)

## Verification

- `cd pickem && ../venv/bin/python manage.py test pickem_api.tests.test_family_logo_storage --settings=pickem.test_settings --verbosity=2` — passed (7 tests).
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyLogoUploadFoundationTests --settings=pickem.test_settings --verbosity=1` — passed (68 tests).
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=1` — passed (441 tests).
- `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` — passed.

## Deviations from Plan

None - plan executed as written.

## User Setup Required

None for this application plan. The dedicated AWS/ESO identity and secret delivery are owned by Plan 02.

## Next Phase Readiness

The application is ready for Plan 02 to supply the dedicated `FAMILY_LOGO_*` Secret through IAM, Secrets Manager, and ESO. Local development continues to use filesystem media when that secret is absent.
