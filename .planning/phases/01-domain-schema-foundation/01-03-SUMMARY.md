---
phase: 01-domain-schema-foundation
plan: 03
subsystem: database
tags: [django, migrations, multi-tenancy, message-board, banners, admin, tests]

requires:
  - phase: 01-domain-schema-foundation
    provides: core Family and FamilyMembership schema plus legacy pool/membership backfill from Plans 01 and 02
provides:
  - Nullable family scope on homepage banner and message-board tables
  - Idempotent homepage message-board family backfill
  - Message-board-only active user membership coverage for the deterministic legacy family
  - Admin visibility for homepage family assignments
affects: [family-scoped-app-pages, family-admin, production-migration, authorization-foundation]

tech-stack:
  added: []
  patterns:
    - Nullable-first family FK expansion before route/query enforcement
    - Historical-model RunPython backfill with deterministic legacy family reuse
    - Site-wide nullable banner behavior preserved while family-specific banners become representable

key-files:
  created:
    - pickem/pickem_homepage/migrations/0005_add_family_scope.py
  modified:
    - pickem/pickem_homepage/models.py
    - pickem/pickem_homepage/admin.py
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "SiteBanner.family remains nullable and existing banner rows stay family=NULL so current site-wide banner behavior is preserved."
  - "Homepage family backfill depends on pickem_api.0074_add_legacy_pool_scope so existing Plan 02 legacy memberships are present before adding message-board-only members."
  - "MessageBoardComment.family is derived from post.family and MessageBoardVote.family is derived from the vote's post or comment target."

patterns-established:
  - "Homepage-owned tenant data uses direct nullable Family foreign keys with safe non-unique indexes."
  - "Homepage migration helpers preserve existing owner/admin membership roles and only add active member coverage."
  - "Admin list displays, filters, fields, and searches include tenant fields without removing existing admin behavior."

requirements-completed: [TEN-05, COMM-01, COMM-03]

coverage:
  - id: D1
    description: "SiteBanner, MessageBoardPost, MessageBoardComment, and MessageBoardVote have nullable family foreign keys with safe lookup indexes."
    requirement: COMM-01
    verification:
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings"
        status: pass
      - kind: unit
        ref: "pickem/pickem_homepage/tests.py#HomepageFamilyScopeModelTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Existing message-board rows are backfilled to the deterministic legacy family, with comments deriving from posts and votes deriving from post/comment targets."
    requirement: COMM-01
    verification:
      - kind: unit
        ref: "pickem/pickem_homepage/tests.py#HomepageFamilyBackfillMigrationTests.test_backfill_assigns_message_board_rows_to_legacy_family_and_leaves_banners_site_wide"
        status: pass
      - kind: unit
        ref: "pickem/pickem_homepage/tests.py#HomepageFamilyBackfillMigrationTests.test_comment_and_vote_family_backfill_derive_from_targets"
        status: pass
    human_judgment: false
  - id: D3
    description: "Active users with only message-board post, comment, or vote activity receive active legacy member memberships, while inactive users are skipped and elevated roles are preserved."
    requirement: TEN-05
    verification:
      - kind: unit
        ref: "pickem/pickem_homepage/tests.py#HomepageFamilyBackfillMigrationTests.test_backfill_creates_member_memberships_for_message_board_only_active_users"
        status: pass
      - kind: unit
        ref: "pickem/pickem_homepage/tests.py#HomepageFamilyBackfillMigrationTests.test_backfill_preserves_existing_elevated_roles_and_skips_inactive_users"
        status: pass
    human_judgment: false
  - id: D4
    description: "Existing site banners remain valid with family=NULL and active-banner lookup behavior is unchanged."
    requirement: COMM-03
    verification:
      - kind: unit
        ref: "pickem/pickem_homepage/tests.py#SiteBannerModelTests.test_site_wide_banner_can_remain_family_null_and_active"
        status: pass
    human_judgment: false
  - id: D5
    description: "Homepage family assignments are visible and filterable in Django admin for banners, posts, comments, and votes."
    requirement: COMM-01
    verification:
      - kind: unit
        ref: "pickem/pickem_homepage/tests.py#HomepageFamilyScopeAdminTests.test_admin_classes_expose_family_for_homepage_scope"
        status: pass
      - kind: integration
        ref: "cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-06-28
status: complete
---

# Phase 01 Plan 03: Homepage Family Scope Summary

**Nullable family scope and legacy message-board backfill for homepage banners, posts, comments, votes, memberships, and admin inspection.**

## Performance

- **Duration:** 10min
- **Started:** 2026-06-28T18:41:30Z
- **Completed:** 2026-06-28T18:51:32Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added nullable `family` FKs to `SiteBanner`, `MessageBoardPost`, `MessageBoardComment`, and `MessageBoardVote`.
- Added safe non-unique family lookup indexes for homepage banner and message-board tables.
- Implemented `0005_add_family_scope.py` with idempotent message-board row backfill and active message-board-only legacy memberships.
- Preserved current site-wide banner behavior by leaving existing `SiteBanner.family` values null.
- Exposed homepage family assignments in Django admin list displays, filters, fields, and searches.

## Task Commits

1. **Task 1: Add homepage family-scope tests** - `cf75943` (test)
2. **Task 2: Add nullable family fields and homepage backfill migration** - `48f17ca` (feat)
3. **Task 3: Expose homepage family fields in admin** - `86ad450` (feat)

## Files Created/Modified

- `pickem/pickem_homepage/models.py` - Adds nullable family FKs and safe indexes for homepage tenant-owned rows.
- `pickem/pickem_homepage/migrations/0005_add_family_scope.py` - Adds family fields/indexes and backfills legacy message-board family scope and memberships.
- `pickem/pickem_homepage/admin.py` - Adds family visibility and filtering for banners, posts, comments, and votes.
- `pickem/pickem_homepage/tests.py` - Adds focused model, migration-helper, banner, and admin tests.

## Decisions Made

- Kept `SiteBanner.family` nullable and did not assign existing banners to the legacy family so `family=NULL` remains the site-wide banner representation.
- Used direct nullable family fields on comments and votes rather than relying only on joins, matching the threat model's query-safety guidance.
- Made homepage migration `0005` depend on `pickem_api.0074_add_legacy_pool_scope` so Plan 02 memberships exist before adding message-board-only members.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Sequenced homepage backfill after Plan 02 membership backfill**
- **Found during:** Task 2
- **Issue:** The written task named `pickem_api.0073_domain_schema_foundation` as the cross-app dependency, but preserving existing Plan 02 owner/admin memberships requires the Plan 02 data migration to have run first.
- **Fix:** Made `pickem_homepage.0005_add_family_scope` depend on `pickem_api.0074_add_legacy_pool_scope`, which transitively depends on `0073`.
- **Files modified:** `pickem/pickem_homepage/migrations/0005_add_family_scope.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `48f17ca`

**2. [Rule 1 - Bug] Fixed migration-helper test setup for protected legacy pool**
- **Found during:** Task 2
- **Issue:** The RED migration tests attempted to delete the deterministic legacy family, but Plan 02's migrated test database already has a protected `Pool.family` reference.
- **Fix:** Reused the deterministic legacy family in tests and cleared only relevant memberships.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `48f17ca`

**Total deviations:** 2 auto-fixed (1 missing critical functionality, 1 bug)
**Impact on plan:** Both fixes preserved the intended schema/backfill behavior and avoided scope creep.

## Issues Encountered

- Django continues to report 13 pre-existing `userStats` `IntegerField(max_length=...)` warnings during checks/tests. These were documented by prior plans and were not modified.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None - the migration/admin/database surface is covered by the plan threat model and no route, auth, file-access, network endpoint, template, CSS, or JavaScript behavior changed.

## Verification

- PASS: `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings`
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings`
- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2`
- PASS: RED gate failed before implementation on missing family fields, missing migration module, and missing admin family exposure.

## Next Phase Readiness

Plan 01-04 can run final Phase 1 verification across all schema foundation work.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/01-domain-schema-foundation/01-03-SUMMARY.md`.
- Task commits exist: `cf75943`, `48f17ca`, `86ad450`.
- Created migration exists at `pickem/pickem_homepage/migrations/0005_add_family_scope.py`.
- No unrelated dirty homepage CSS/template/view files were staged or committed.

---
*Phase: 01-domain-schema-foundation*
*Completed: 2026-06-28*
