---
phase: 03-onboarding-and-family-selection
plan: 02
subsystem: onboarding-create-family
tags: [django, tenant-onboarding, csrf, transactions, templates, tests]

requires:
  - phase: 01-domain-schema-foundation
    provides: [Family, Pool, PoolSettings, FamilyMembership, FamilyAuditLog tenant domain models]
  - phase: 02-authorization-foundation
    provides: [family_member_required tenant entry guard]
  - phase: 03-onboarding-and-family-selection
    provides: [post-login onboarding shell and tenant pool entry route]
provides:
  - Authenticated create-family flow that creates a default current-season NFL pool.
  - Server-owned owner membership, role, status, season, family, and pool assignment.
  - CSRF-protected POST mutation with focused regression coverage.
  - Create-family template wired from onboarding.
affects: [phase-03-onboarding-and-family-selection, phase-04-family-scoped-app-pages, phase-05-family-admin-experience]

tech-stack:
  added: []
  patterns: [Django Form validation, transaction.atomic tenant creation, deterministic slug generation, audit-backed onboarding mutation]

key-files:
  created:
    - pickem/pickem_homepage/templates/pickem/create_family.html
  modified:
    - pickem/pickem_homepage/forms.py
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/templates/pickem/onboarding.html
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Create-family accepts only a family name; all tenant, owner, role, status, season, and pool values are server-derived."
  - "Default created pool is named Main Pickem, uses slug main-pickem, competition nfl, current season, active status, and is_default true."
  - "Audit logging uses membership_created for owner creation and pool_settings_updated metadata for default-pool creation because the existing audit action enum has no family_created or pool_created action."

patterns-established:
  - "Tenant onboarding writes Family, Pool, PoolSettings, FamilyMembership, and FamilyAuditLog rows inside one transaction.atomic block."
  - "Unique family slugs are generated deterministically by appending numeric suffixes."
  - "Create-family templates render field errors inline and rely on standard Django CSRF middleware."

requirements-completed: [TEN-01, AUTHZ-01, AUD-01]

coverage:
  - id: D1
    description: "Authenticated users can create a family by submitting only a family name."
    requirement: TEN-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.CreateFamilyFlowTests.test_valid_post_creates_family_default_pool_settings_owner_and_audit"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.CreateFamilyFlowTests.test_client_supplied_tenant_and_role_fields_are_ignored"
        status: pass
    human_judgment: false
  - id: D2
    description: "Create-family creates the default pool, pool settings, owner membership, and audit rows in one server-owned flow."
    requirement: TEN-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.CreateFamilyFlowTests.test_valid_post_creates_family_default_pool_settings_owner_and_audit"
        status: pass
    human_judgment: false
  - id: D3
    description: "Create-family mutation is login-required and CSRF-protected."
    requirement: AUTHZ-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.CreateFamilyFlowTests.test_create_family_requires_login"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.CreateFamilyFlowTests.test_create_family_post_requires_csrf_token"
        status: pass
    human_judgment: false
  - id: D4
    description: "Onboarding links to create-family and the create-family form renders validation errors."
    requirement: TEN-01
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.CreateFamilyFlowTests.test_onboarding_links_to_create_family_route"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.CreateFamilyFlowTests.test_create_family_form_renders_validation_errors"
        status: pass
    human_judgment: false

duration: 4min 10s
completed: 2026-06-29
status: complete
---

# Phase 03 Plan 02: Create-Family Flow With Default Pool Summary

Authenticated users can create a private family and default current-season NFL pool through one CSRF-protected onboarding flow.

## Performance

- **Duration:** 4min 10s
- **Started:** 2026-06-29T13:03:00Z
- **Completed:** 2026-06-29T13:07:10Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added create-family coverage for login, CSRF, deterministic slug collisions, server-owned field handling, default pool creation, owner membership, pool settings, and audit rows.
- Added `CreateFamilyForm`, `/families/create/`, and a `transaction.atomic()` create path for `Family`, `Pool`, `PoolSettings`, `FamilyMembership`, and `FamilyAuditLog`.
- Added the create-family template and wired onboarding's create action to the named route.

## Task Commits

1. **Task 1: Add create-family tests** - `f56e041` (test)
2. **Task 2: Implement transactional create-family flow** - `98e74da` (feat)
3. **Task 3: Wire create-family template from onboarding** - `485ff1f` (feat)

**Plan metadata:** recorded in the final `docs(03-02)` commit.

## Files Created/Modified

- `pickem/pickem_homepage/forms.py` - Added `CreateFamilyForm` with a single normalized family-name field.
- `pickem/pickem_homepage/views.py` - Added unique slug generation and transactional create-family logic with audit rows.
- `pickem/pickem_homepage/urls.py` - Added `families/create/` named `create_family`.
- `pickem/pickem_homepage/templates/pickem/create_family.html` - Added the create-family form page with CSRF and error rendering.
- `pickem/pickem_homepage/templates/pickem/onboarding.html` - Linked the create action to the named create-family route.
- `pickem/pickem_homepage/tests.py` - Added create-family integration tests.

## Decisions Made

- Used a family-name-only form to prevent client control of tenant IDs, owner IDs, roles, statuses, pool season, or default-pool fields.
- Used `Main Pickem` / `main-pickem` as the default pool name/slug for each newly created family.
- Used existing audit action types for equivalent security-sensitive records because the schema does not currently include `family_created` or `pool_created` actions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Scoped validation-error test around legacy migration data**
- **Found during:** Task 3
- **Issue:** The invalid-form test initially asserted no `Family` rows existed, but test migrations can create a legacy family row unrelated to the create-family submission.
- **Fix:** Changed the assertion to compare the family row count before and after the invalid POST.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `485ff1f`

**2. [Rule 2 - Missing critical verification] Added UI wiring assertions during template task**
- **Found during:** Task 3
- **Issue:** The plan's Task 3 acceptance criteria required proof that onboarding exposes create-family and validation errors render, but the initial Task 1 tests focused on backend creation behavior.
- **Fix:** Added focused tests for the onboarding create link and create-family validation error rendering.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `485ff1f`

**Total deviations:** 2 auto-fixed (Rule 1: 1, Rule 2: 1)  
**Impact on plan:** Both were limited to correctness and acceptance-criteria coverage; no scope expansion beyond 03-02.

## Known Stubs

- `pickem/pickem_homepage/templates/pickem/onboarding.html` still includes the join-by-code form targeting `/families/join/`; this is the intentional 03-01 shell path owned by 03-03.

## Threat Flags

None. The new authenticated POST route was explicitly in plan scope and is covered by login, CSRF, server-owned field, and audit tests.

## Verification

- `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` - passed, 58 tests.
- `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings` - passed, no changes detected.

Both commands reported the 13 pre-existing `pickem_api.userStats` `IntegerField(max_length=...)` warnings.

## Issues Encountered

None beyond the auto-fixed test assertion noted under deviations.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

03-03 can replace the remaining join-family onboarding shell with invite creation and acceptance. The create-family path now lands users in a protected tenant pool URL, with owner membership and audit trail already present for future invite ownership checks.

## Self-Check: PASSED

- Created file exists: `pickem/pickem_homepage/templates/pickem/create_family.html`.
- Modified files exist: `forms.py`, `views.py`, `urls.py`, `onboarding.html`, and `tests.py`.
- Task commits exist: `f56e041`, `98e74da`, `485ff1f`.
- No tracked files were deleted by task commits.

---
*Phase: 03-onboarding-and-family-selection*
*Completed: 2026-06-29*
