---
phase: 01-domain-schema-foundation
plan: 01
subsystem: database
tags: [django, models, migrations, admin, tests, multi-tenancy]

requires:
  - phase: 01-domain-schema-foundation
    provides: approved Phase 1 context, research, patterns, and validation criteria
provides:
  - Core tenant domain models for family, pool, membership, settings, invitation, and audit logging
  - Additive Django migration for new tenant-domain tables only
  - Django admin registrations for tenant-domain inspection
  - Focused model/admin tests for TEN-02, TEN-03, TEN-04, and SEC-01
affects: [authorization-foundation, onboarding, family-admin, migration-hardening]

tech-stack:
  added: []
  patterns:
    - Additive Django schema migration with new-table constraints and indexes
    - TextChoices plus portable CheckConstraint for role/status/action fields
    - Hashed invitation code storage only; no raw invite code field

key-files:
  created:
    - pickem/pickem_api/migrations/0073_domain_schema_foundation.py
  modified:
    - pickem/pickem_api/models.py
    - pickem/pickem_api/admin.py
    - pickem/pickem_api/tests.py

key-decisions:
  - "Family and Pool were implemented as separate first-class models."
  - "NFL reference tables GamesAndScores, GameWeeks, and Teams were left global and unchanged."
  - "FamilyInvitation stores code_hash only; raw invite codes are not represented in model, admin, or tests."
  - "FamilyAuditLog is append-oriented storage for later sensitive-action wiring; no runtime route behavior was changed."

patterns-established:
  - "Tenant domain models use created_at/updated_at, readable __str__, verbose names, deterministic ordering, and explicit indexes."
  - "New tenant choice fields use both Django choices and database CheckConstraint backstops."
  - "Admin registrations expose inspectable tenant data while keeping audit metadata readonly and invite raw secrets absent."

requirements-completed: [TEN-02, TEN-03, TEN-04, SEC-01]

coverage:
  - id: D1
    description: "Core Family, Pool, FamilyMembership, PoolSettings, FamilyInvitation, and FamilyAuditLog models exist with safe new-table constraints and indexes."
    requirement: TEN-02
    verification:
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings"
        status: pass
      - kind: unit
        ref: "pickem/pickem_api/tests.py#TenantDomainModelTest"
        status: pass
    human_judgment: false
  - id: D2
    description: "Membership supports owner/admin/member roles, active/inactive status, multi-family users, and unique family-user membership."
    requirement: TEN-03
    verification:
      - kind: unit
        ref: "pickem/pickem_api/tests.py#TenantDomainModelTest.test_membership_allows_user_in_multiple_families_and_rejects_duplicate_family_user"
        status: pass
    human_judgment: false
  - id: D3
    description: "Invitation storage contains only code_hash and lifecycle fields, with no raw invite-code field exposed."
    requirement: SEC-01
    verification:
      - kind: unit
        ref: "pickem/pickem_api/tests.py#TenantDomainModelTest.test_family_invitation_stores_hash_only_and_lifecycle_fields"
        status: pass
      - kind: unit
        ref: "pickem/pickem_api/tests.py#TenantDomainAdminTest.test_invitation_admin_displays_hash_without_raw_code_fields"
        status: pass
    human_judgment: false
  - id: D4
    description: "Tenant domain models are registered in Django admin and audit metadata is readonly."
    requirement: SEC-01
    verification:
      - kind: unit
        ref: "pickem/pickem_api/tests.py#TenantDomainAdminTest"
        status: pass
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings"
        status: pass
    human_judgment: false

duration: 3min 40s
completed: 2026-06-28
status: complete
---

# Phase 01 Plan 01: Core Tenant Domain Schema Summary

**Django family/pool tenant schema with hashed invitations, audit storage, admin visibility, and focused model tests.**

## Performance

- **Duration:** 3min 40s
- **Started:** 2026-06-28T18:30:27Z
- **Completed:** 2026-06-28T18:34:07Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `Family`, `Pool`, `FamilyMembership`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog` in `pickem_api.models`.
- Generated `0073_domain_schema_foundation.py` as an additive migration that creates only new tenant-domain tables.
- Added model/admin tests covering uniqueness, roles/statuses, one-to-one settings, hashed invitation storage, audit metadata, and admin registration.
- Registered every tenant domain model in Django admin without exposing raw invite secrets.

## Task Commits

1. **Task 1: Add tenant domain model tests first** - `7ccfde9` (test)
2. **Task 2: Implement core family, pool, invitation, and audit models** - `9caa39c` (feat)
3. **Task 3: Register tenant domain models in Django admin** - `ec5bd01` (feat)

## Files Created/Modified

- `pickem/pickem_api/models.py` - Adds tenant domain models, constraints, indexes, and safe deletion behavior.
- `pickem/pickem_api/migrations/0073_domain_schema_foundation.py` - Creates the new tenant-domain tables with constraints and indexes.
- `pickem/pickem_api/admin.py` - Registers admin classes for the new tenant domain models.
- `pickem/pickem_api/tests.py` - Adds focused tenant domain and admin tests.

## Decisions Made

- Implemented `Family` and `Pool` separately so later phases can support multiple pools per family without schema replacement.
- Used `PROTECT` for tenant container relationships and `SET_NULL` for optional historical actor/pool links where preserving audit history matters.
- Added database `CheckConstraint` entries for choice fields because Django `choices` alone do not enforce values at the database layer.
- Left `GamesAndScores`, `GameWeeks`, and `Teams` unchanged per D-06/D-07.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed RED test timedelta reference**
- **Found during:** Task 2
- **Issue:** The RED test used `timezone.timedelta`, which would fail after the model imports were implemented.
- **Fix:** Imported `datetime.timedelta` and used it for invitation expiry.
- **Files modified:** `pickem/pickem_api/tests.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `9caa39c`

**2. [Rule 3 - Blocking] Shortened generated index name**
- **Found during:** Task 2
- **Issue:** Django rejected `membership_family_user_status_idx` because it exceeded the 30-character index-name limit.
- **Fix:** Renamed the index to `member_family_user_status_idx`.
- **Files modified:** `pickem/pickem_api/models.py`, `pickem/pickem_api/migrations/0073_domain_schema_foundation.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py makemigrations pickem_api --settings=pickem.test_settings`
- **Committed in:** `9caa39c`

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking issue)
**Impact on plan:** Both fixes were required for correctness and did not expand scope.

## Issues Encountered

- The Context7 CLI fallback (`ctx7`) was not installed, so no external documentation lookup was available through that path. Implementation followed the project’s pinned Django 4.0.2 patterns and verified behavior with Django management commands.
- Django check continues to report 13 pre-existing `userStats` `IntegerField(max_length=...)` warnings. These were already documented in planning state and were not modified.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None - this plan adds database/admin/test surface already covered by the plan threat model and does not add network endpoints, auth paths, file access, or route behavior.

## Verification

- PASS: `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings`
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings`
- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings --verbosity=2`
- PASS: AST acceptance check confirmed `Teams`, `GamesAndScores`, and `GameWeeks` have no `family` or `pool` fields.
- PASS: Migration inspection found no `AddField`, `AlterField`, `RemoveField`, or `RunPython`; `0073` only creates new tenant-domain tables and their constraints/indexes.

## Next Phase Readiness

Plan 01-02 can add nullable pool scope and legacy competition data backfill using these new domain tables.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/01-domain-schema-foundation/01-01-SUMMARY.md`.
- Task commits exist: `7ccfde9`, `9caa39c`, `ec5bd01`.
- Created migration exists at `pickem/pickem_api/migrations/0073_domain_schema_foundation.py`.
- No unrelated dirty user files were staged or committed.

---
*Phase: 01-domain-schema-foundation*
*Completed: 2026-06-28*
