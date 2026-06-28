---
phase: 01-domain-schema-foundation
plan: 02
subsystem: database
tags: [django, migrations, multi-tenancy, pools, backfill, admin, tests]

requires:
  - phase: 01-domain-schema-foundation
    provides: core Family, Pool, FamilyMembership, and PoolSettings schema from Plan 01
provides:
  - Nullable pool scope on legacy competition tables
  - Idempotent legacy family, pool, settings, membership, and competition-row backfill
  - Admin visibility for competition pool assignment
  - Focused tests for nullable-first safety, owner fallback, idempotence, missing-user tolerance, and role preservation
affects: [authorization-foundation, family-scoped-app-pages, scoring-hardening, production-migration]

tech-stack:
  added: []
  patterns:
    - Nullable-first tenant FK expansion before route/write-path migration
    - Historical-model RunPython backfill with get_or_create idempotence
    - Role-preserving membership derivation from legacy competition and owner fallback sources

key-files:
  created:
    - pickem/pickem_api/migrations/0074_add_legacy_pool_scope.py
  modified:
    - pickem/pickem_api/models.py
    - pickem/pickem_api/admin.py
    - pickem/pickem_api/tests.py

key-decisions:
  - "Legacy competition rows use nullable Pool foreign keys in Phase 1; non-null enforcement and strict tenant uniqueness remain deferred."
  - "The default legacy pool slug is `<season>-pickem` when currentSeason exists, otherwise `legacy-pickem` with fallback season 2024."
  - "Plan 02 reads message-board activity only for the no-owner fallback; Plan 03 remains responsible for message-board family/member coverage."

patterns-established:
  - "Legacy competition tables get non-unique pool lookup indexes only."
  - "Backfill helpers preserve existing owner/admin memberships when adding member coverage."
  - "Reverse migration clears competition pool FKs but leaves deterministic legacy domain rows in place."

requirements-completed: [TEN-02, TEN-03, TEN-04, TEN-05, POOL-01, POOL-02]

coverage:
  - id: D1
    description: "GamePicks, userSeasonPoints, retained userPoints, and userStats have nullable Pool foreign keys with safe non-unique lookup indexes."
    requirement: POOL-01
    verification:
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings"
        status: pass
      - kind: unit
        ref: "pickem/pickem_api/tests.py#LegacyPoolScopeModelTest"
        status: pass
    human_judgment: false
  - id: D2
    description: "Legacy competition rows are backfilled to a deterministic legacy pool without mutating legacy denormalized user fields."
    requirement: TEN-05
    verification:
      - kind: unit
        ref: "pickem/pickem_api/tests.py#LegacyPoolBackfillMigrationTest.test_backfill_creates_legacy_pool_assigns_rows_and_preserves_roles_idempotently"
        status: pass
    human_judgment: false
  - id: D3
    description: "Legacy membership derivation maps active superusers to owner, commissioners to admin or owner fallback, active competition users to member, and preserves existing elevated roles."
    requirement: TEN-03
    verification:
      - kind: unit
        ref: "pickem/pickem_api/tests.py#LegacyPoolBackfillMigrationTest"
        status: pass
    human_judgment: false
  - id: D4
    description: "Competition pool assignment is inspectable in Django admin for picks, standings, retained points, and stats."
    verification:
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-06-28
status: complete
---

# Phase 01 Plan 02: Legacy Competition Pool Scope Summary

**Nullable pool scope and idempotent legacy competition backfill for picks, standings, retained user points, and stats.**

## Performance

- **Duration:** 5min
- **Started:** 2026-06-28T18:39:13Z
- **Completed:** 2026-06-28T18:43:49Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added nullable `pool` FKs to `GamePicks`, `userSeasonPoints`, retained `userPoints`, and `userStats`.
- Added safe non-unique indexes for pool/season/week/user lookup without adding strict legacy uniqueness.
- Implemented `0074_add_legacy_pool_scope.py` with an idempotent `RunPython` backfill for legacy family, pool, settings, memberships, and competition rows.
- Added admin list display/filter visibility for competition `pool` assignment.
- Added focused tests covering nullable fields, idempotence, superuser/commissioner/member mapping, owner fallback, role preservation, and missing-user tolerance.

## Task Commits

1. **Task 1: Add legacy pool-scope tests** - `c9681d4` (test)
2. **Task 2: Add nullable pool fields and safe indexes** - `36fd1c1` (feat)
3. **Task 3: Implement idempotent legacy family, pool, membership, and competition backfill** - `513fa3d` (feat)

## Files Created/Modified

- `pickem/pickem_api/models.py` - Adds nullable `pool` FKs and non-unique lookup indexes to legacy competition tables.
- `pickem/pickem_api/migrations/0074_add_legacy_pool_scope.py` - Adds pool fields/indexes and backfills deterministic legacy pool scope.
- `pickem/pickem_api/admin.py` - Shows and filters competition rows by `pool`.
- `pickem/pickem_api/tests.py` - Adds legacy pool-scope and migration-helper tests.

## Decisions Made

- Used `<season>-pickem` when `currentSeason.season` exists and `legacy-pickem` with season `2024` as the deterministic fallback.
- Kept `pool` nullable and avoided `GamePicks(pool, uid, pick_game_id)` or standings uniqueness per Phase 1 constraints.
- Limited message-board reads to owner fallback only so Plan 03 can own message-board family backfill and membership coverage.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted RED tests for migrated test database state**
- **Found during:** Task 3
- **Issue:** The RED tests created `Family(slug="legacy-family-league")`, but the implemented migration creates that family during Django test database setup.
- **Fix:** Used a distinct family slug for pure model tests and cleared deterministic legacy rows in migration-helper tests before each direct helper run.
- **Files modified:** `pickem/pickem_api/tests.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `513fa3d`

**2. [Rule 1 - Bug] Corrected owner-fallback test ordering**
- **Found during:** Task 3
- **Issue:** The RED test intended to prove earliest active referenced user fallback but created the competition user before the message-board user while expecting the message-board user to be owner.
- **Fix:** Created the message-board user first so the assertion matches the intended earliest-user behavior.
- **Files modified:** `pickem/pickem_api/tests.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `513fa3d`

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes kept the tests aligned with the planned migration behavior and did not expand scope.

## Issues Encountered

- Django continues to report 13 pre-existing `userStats` `IntegerField(max_length=...)` warnings. They were not introduced or modified by this plan.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None - the new migration/admin/database surface is covered by the plan threat model and no route, auth, file-access, or network endpoint behavior changed.

## Verification

- PASS: `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings`
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings`
- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings --verbosity=2`
- PASS: `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2`

## Next Phase Readiness

Plan 01-03 can add nullable family scope to homepage community/banner data. Plan 01-04 can run final Phase 1 verification after both Wave 2 implementation plans are complete.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/01-domain-schema-foundation/01-02-SUMMARY.md`.
- Task commits exist: `c9681d4`, `36fd1c1`, `513fa3d`.
- Created migration exists at `pickem/pickem_api/migrations/0074_add_legacy_pool_scope.py`.
- No unrelated dirty user files were staged or committed.

---
*Phase: 01-domain-schema-foundation*
*Completed: 2026-06-28*
