---
phase: 06-secure-logo-foundation
plan: "02"
subsystem: storage
tags: [django, s3, django-storages, migration, family-logo]
requires:
  - phase: 06-secure-logo-foundation
    provides: Decoder-verified canonical WebP processor
provides:
  - Private prefix-scoped FamilyLogoStorage for generated WebP assets
  - Nullable Family.logo reference with UUID-derived server-owned object names
  - Removal of Family logo URL editors and safe static default rendering
affects: [06-03, 07-commissioner-upload-and-delivery-experience, 08-private-aws-delivery-and-adversarial-verification]
tech-stack:
  added: []
  patterns: [dedicated S3 storage subclass, server-derived upload keys, null-logo static fallback]
key-files:
  created:
    - pickem/pickem_api/storage.py
    - pickem/pickem_api/migrations/0090_replace_family_logo_url.py
    - pickem/pickem_api/tests/test_family_logo_storage.py
  modified:
    - pickem/pickem_api/models.py
    - pickem/pickem_api/admin.py
    - pickem/pickem_homepage/forms.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/templates/pickem/family_pool_home.html
    - pickem/pickem_homepage/templates/pickem/family_picker.html
    - pickem/pickem_superadmin/forms.py
    - pickem/pickem_superadmin/templates/superadmin/families.html
key-decisions:
  - "Use a dedicated private S3 storage prefix with signed URLs and immutable WebP metadata."
  - "Delete legacy arbitrary URL values without fetching or adopting remote content."
  - "Represent a missing canonical logo with the existing static default rather than a URL fallback."
patterns-established:
  - "Family logo object keys derive only from the saved Family id and UUID; browser filenames are ignored."
  - "Dedicated storage behavior is checked by introspection under local test settings, never by live AWS calls."
requirements-completed: [IMG-03, S3-01]
coverage:
  - id: D1
    description: Family logo object keys are server-derived WebP names below the private family-logos prefix.
    requirement: S3-01
    verification:
      - kind: unit
        ref: pickem_api.tests.test_family_logo_storage.FamilyLogoStorageTests
        status: pass
    human_judgment: false
  - id: D2
    description: Family persistence stores only an optional canonical logo reference and never a legacy arbitrary URL.
    requirement: IMG-03
    verification:
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings"
        status: pass
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py test pickem_api.tests.test_family_logo_storage pickem_homepage.tests pickem_superadmin.tests.test_families --settings=pickem.test_settings"
        status: pass
    human_judgment: false
duration: 18 min
completed: 2026-07-18
status: complete
---

# Phase 06 Plan 02: Managed family-logo storage and URL retirement Summary

**Families now retain only a nullable, server-owned canonical logo reference backed by a dedicated private S3 prefix.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-18T21:24:00Z
- **Completed:** 2026-07-18T21:42:00Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments

- Added a private FamilyLogoStorage with signed access, generated-key protection, and fixed WebP cache/content metadata.
- Replaced Family.logo_url with nullable Family.logo in a non-fetching migration.
- Removed family URL editors and render dependencies while preserving static-default logo fallbacks.

## Task Commits

1. **Task 1: Specify generated key, local-storage, and legacy-fallback invariants** - e559b27 (test)
2. **Task 2: Add dedicated logo storage and replace the Family schema safely** - c938ff5 (feat)
3. **Task 3: Remove every unsafe family URL editor and keep existing family pages safe** - 0a98fc4 (refactor)

## Files Created/Modified

- pickem/pickem_api/storage.py - Private S3 storage contract for processed family logos.
- pickem/pickem_api/models.py - Family.logo and server-generated upload key callable.
- pickem/pickem_api/migrations/0090_replace_family_logo_url.py - Schema-only transition with no remote fetch.
- pickem/pickem_api/tests/test_family_logo_storage.py - Offline storage/key regression coverage.
- pickem/pickem_homepage/templates/pickem/family_pool_home.html - Canonical-logo/static-default rendering.

## Decisions Made

- Kept the existing bucket configuration and isolated logo behavior in a dedicated django-storages subclass.
- Legacy URL data is removed rather than copied or fetched, preventing migration-time SSRF and unsafe adoption.
- Phase 06 foundation pages render the existing static logo whenever Family.logo is null; upload UI belongs to Plan 03.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking runtime import] Removed the superadmin URL field while adding the schema transition.**
- **Found during:** Task 2 (Add dedicated logo storage and replace the Family schema safely)
- **Issue:** Django imports FamilyRowForm during system checks, so retaining its removed logo_url model field caused FieldError before focused storage tests could run.
- **Fix:** Removed the superadmin URL editor and replaced its table cell with a non-editable configured/default state.
- **Files modified:** pickem/pickem_superadmin/forms.py, pickem/pickem_superadmin/templates/superadmin/families.html, pickem/pickem_superadmin/tests/test_families.py
- **Verification:** Focused superadmin and homepage suites pass after the migration.
- **Committed in:** 0a98fc4 (part of Task 3)

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking runtime import).  
**Impact on plan:** Required to make the schema removal load safely; it directly fulfills the plan's URL-editor removal requirement with no scope expansion.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 06-03 can attach its authorized multipart form to Family.logo; generated keys, private storage semantics, and no-logo fallbacks are ready.

## Self-Check: PASSED

---
*Phase: 06-secure-logo-foundation*  
*Completed: 2026-07-18*
