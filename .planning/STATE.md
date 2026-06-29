---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planned
stopped_at: Completed 03-05-PLAN.md
last_updated: "2026-06-29T13:41:30Z"
progress:
  total_phases: 8
  completed_phases: 3
  total_plans: 12
  completed_plans: 12
  percent: 100
---

# GSD State

**Project:** Family Pickem Multi-Tenancy  
**Updated:** 2026-06-29 after Phase 3 Plan 05 verification

## Project Reference

See: `.planning/PROJECT.md`

**Core value:** Families can run private pick'em pools with strict server-enforced data isolation.  
**Current focus:** Phase 04 — family-scoped app pages

## Completed

- Discovery of current Django architecture, domain models, routes/APIs, security risks, UX gaps, and migration risks.
- Documentation-only discovery artifacts created at repo root.
- GSD project context, requirements, roadmap, and state initialized.
- Existing Django checks/tests run with repository virtualenv.
- Phase 1 planned as four independently reviewable plans:
  - `01-01-PLAN.md`: core family/pool/membership/invitation/audit schema.
  - `01-02-PLAN.md`: nullable pool scope and legacy competition data backfill.
  - `01-03-PLAN.md`: nullable family scope for homepage community and banner data.
  - `01-04-PLAN.md`: dependent final Phase 1 verification.
- Phase 1 plan checker passed after revision.
- Phase 1 Plan 01 completed:
  - Added `Family`, `Pool`, `FamilyMembership`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog`.
  - Added additive migration `pickem_api.0073_domain_schema_foundation`.
  - Added tenant domain admin registrations and focused model/admin tests.
  - Summary: `.planning/phases/01-domain-schema-foundation/01-01-SUMMARY.md`.
- Phase 1 Plan 02 completed:
  - Added nullable `pool` scope to `GamePicks`, `userSeasonPoints`, retained `userPoints`, and `userStats`.
  - Added additive/backfill migration `pickem_api.0074_add_legacy_pool_scope`.
  - Added idempotent legacy family/pool/settings/membership backfill with owner fallback and role preservation.
  - Added admin pool visibility and focused pool-scope/backfill tests.
  - Summary: `.planning/phases/01-domain-schema-foundation/01-02-SUMMARY.md`.
- Phase 1 Plan 03 completed:
  - Added nullable `family` scope to `SiteBanner`, `MessageBoardPost`, `MessageBoardComment`, and `MessageBoardVote`.
  - Added additive/backfill migration `pickem_homepage.0005_add_family_scope`.
  - Added idempotent homepage message-board family backfill and message-board-only active member coverage.
  - Preserved site-wide banner behavior with nullable `SiteBanner.family`.
  - Added admin family visibility and focused homepage family-scope tests.
  - Summary: `.planning/phases/01-domain-schema-foundation/01-03-SUMMARY.md`.
- Phase 1 Plan 04 completed:
  - Verified all implementation summaries and required Phase 1 artifacts exist.
  - Confirmed owner fallback, earliest active referenced user fallback, message-board-only membership, and role-preservation tests are present.
  - Confirmed no pending migrations with `makemigrations --check --dry-run`.
  - Ran focused `pickem_api`, focused `pickem_homepage`, and full Django test suites successfully.
  - Summary: `.planning/phases/01-domain-schema-foundation/01-04-SUMMARY.md`.
- Phase 2 planned as three independently reviewable plans:
  - `02-01-PLAN.md`: core tenant authorization helpers.
  - `02-02-PLAN.md`: view/API guards and proof integration.
  - `02-03-PLAN.md`: final verification and handoff.
- Phase 2 Plan 01 completed:
  - Added `pickem_api.authz` with centralized tenant denial classes, role checks, family/pool resolution, and explicit legacy fallback.
  - Added helper tests for active member access, role denial, inactive/non-member denial, superuser/commissioner non-bypass, pool-family mismatch, cross-family denial, and legacy fallback.
  - Summary: `.planning/phases/02-authorization-foundation/02-01-SUMMARY.md`.
- Phase 2 Plan 02 completed:
  - Added `pickem_homepage.authz.family_member_required`.
  - Added DRF/API denial mapping and `GET /api/families/<family_slug>/pools/<pool_slug>/authz-check/` proof endpoint.
  - Added browser and API integration tests for anonymous, non-member, wrong-role, allowed member/admin/owner, and pool-family mismatch behavior.
  - Summary: `.planning/phases/02-authorization-foundation/02-02-SUMMARY.md`.
- Phase 2 Plan 03 completed:
  - Confirmed no pending migrations.
  - Ran Django check, focused app suites, and full suite successfully.
  - Summary: `.planning/phases/02-authorization-foundation/02-03-SUMMARY.md`.
- Phase 3 planned as five independently reviewable plans:
  - `03-01-PLAN.md`: post-login routing and onboarding shell.
  - `03-02-PLAN.md`: create-family flow with default pool.
  - `03-03-PLAN.md`: minimal invite creation and acceptance.
  - `03-04-PLAN.md`: header/mobile family switcher.
  - `03-05-PLAN.md`: final verification and handoff.
- Phase 3 Plan 01 completed:
  - Added authenticated root routing by active family membership count.
  - Added onboarding, family picker, and protected tenant pool entry shells.
  - Summary: `.planning/phases/03-onboarding-and-family-selection/03-01-SUMMARY.md`.
- Phase 3 Plan 02 completed:
  - Added authenticated create-family flow with a single family-name field.
  - Created `Family`, current-season default NFL `Pool`, `PoolSettings`, owner `FamilyMembership`, and `FamilyAuditLog` rows transactionally.
  - Added CSRF, slug collision, server-owned field, validation-error, onboarding-link, and success redirect tests.
  - Summary: `.planning/phases/03-onboarding-and-family-selection/03-02-SUMMARY.md`.
- Phase 3 Plan 03 completed:
  - Added owner-only minimal member invite creation from family/pool context.
  - Added hash-only invite code storage with one-time raw-code/link display.
  - Added authenticated manual-code and invite-link acceptance with transaction-scoped validation, membership create/reactivation, use counting, and audit logging.
  - Added negative tests for admin/member/outsider invite creation, CSRF, revoked/expired/exhausted/invalid/inactive/mismatched invites, and generic invalid-invite errors.
  - Summary: `.planning/phases/03-onboarding-and-family-selection/03-03-SUMMARY.md`.
- Phase 3 Plan 04 completed:
  - Added server-derived family switcher context for current family, current pool, current membership, and active family choices.
  - Updated desktop and mobile header navigation to show current family/default pool and switch to explicit tenant URLs.
  - Added isolation tests proving inactive memberships and outsider families do not appear in switcher context or markup.
  - Summary: `.planning/phases/03-onboarding-and-family-selection/03-04-SUMMARY.md`.
- Phase 3 Plan 05 completed:
  - Ran final Django check, migration dry-run, focused homepage/API tests, full Django test suite, and local public-home curl spot-check successfully.
  - Updated Phase 3 validation to reference `03-01-SUMMARY.md` through `03-05-SUMMARY.md` and document onboarding, create-family, invite, switcher, and negative authorization coverage.
  - Documented remaining Phase 4 risks for global gameplay pages: dashboard/home, picks, scores, standings, rules, profiles, and message board still need explicit tenant-scoped page/data migration.
  - Summary: `.planning/phases/03-onboarding-and-family-selection/03-05-SUMMARY.md`.

## Decisions

- 01-01: Family and Pool are separate first-class models.
- 01-01: `GamesAndScores`, `GameWeeks`, and `Teams` remain global reference tables with no tenant fields.
- 01-01: `FamilyInvitation` stores `code_hash` only; no raw invite-code model/admin/test field exists.
- 01-02: Legacy competition rows use nullable Pool foreign keys; non-null enforcement and strict tenant uniqueness remain deferred.
- 01-02: Default legacy pool slug is `<season>-pickem` when `currentSeason` exists, otherwise `legacy-pickem` with fallback season 2024.
- 01-02: Plan 02 reads message-board activity only for no-owner fallback; Plan 03 owns message-board family/member coverage.
- 01-03: Site banners remain site-wide when `family` is null; existing banner rows are not forced into the legacy family.
- 01-03: Homepage message-board backfill runs after `pickem_api.0074_add_legacy_pool_scope` so Plan 02 owner/admin roles are preserved.
- 01-03: Comment family scope derives from `post.family`; vote family scope derives from the vote's post or comment target.
- 01-04: Phase 1 final verification passed with no pending migrations, 31 `pickem_api` tests, 40 `pickem_homepage` tests, and 71 full-suite tests passing.
- 02: Tenant authorization helpers must not grant implicit access to `is_superuser` or legacy `UserProfile.is_commissioner`; explicit active `FamilyMembership` is required.
- 02: Anonymous page requests redirect to login; anonymous API/helper denials are auth errors; authenticated non-members get 404; active members lacking role get 403.
- 02: Phase 2 intentionally avoids broad product route migration; later phases own onboarding, page scoping, and family admin migration.
- 02: Proof endpoint is intentionally minimal and returns only family slug, pool slug, and current user's role.
- 03: Signed-in post-login routing is based on active family membership count: zero goes to onboarding, one goes to that family's default pool, multiple goes to picker/switcher.
- 03: Create-family creates one default current-season NFL pool and owner membership in the same flow.
- 03: Join supports invite code/link; minimal owner-created member invites are in Phase 3, while full invite management remains Phase 5.
- 03: Header switcher plus readable `/families/<family_slug>/pools/<pool_slug>/...` URLs are the Phase 3 tenant context model.
- [Phase 03]: 03-01: Authenticated root requests now route by active family membership count before legacy global homepage data is queried.
- [Phase 03]: 03-01: Tenant entry reuses family_member_required for membership and pool-family consistency checks.
- [Phase 03]: 03-01: Create/join onboarding links remain shell entry paths for 03-02 and 03-03.
- [Phase 03]: 03-02: Create-family accepts only a family name; tenant, owner, role, status, season, and pool values are server-derived.
- [Phase 03]: 03-02: Default create-family pool is `Main Pickem` / `main-pickem` for the current NFL season.
- [Phase 03]: 03-02: Existing audit actions are reused for equivalent security-sensitive onboarding records because the audit enum has no family-created action.
- [Phase 03]: 03-03: Phase 3 invite creation is owner-only; full invite management policy remains deferred to Phase 5.
- [Phase 03]: 03-03: Invite links render a confirmation form and require POST for acceptance so membership mutation remains CSRF-protected.
- [Phase 03]: 03-03: Invite codes are normalized for readability, hashed server-side, and stored only in `FamilyInvitation.code_hash`.
- [Phase 03]: 03-04: Switcher choices are derived only from authenticated active memberships via get_user_family_memberships().
- [Phase 03]: 03-04: Current tenant context is resolved through require_tenant_context() before templates receive it.
- [Phase 03]: 03-04: Header switch targets remain default active pools with explicit family/pool URLs; multi-pool UI stays deferred.
- [Phase 03]: 03-05: Final verification passed with 116 focused homepage/API tests and 116 full-suite tests; the only warnings are the pre-existing `userStats` `IntegerField(max_length=...)` warnings.
- [Phase 03]: 03-05: Phase 4 owns tenant-scoping of gameplay pages and data queries; Phase 3 completion does not mark dashboard/picks/scores/standings/rules/profile/message-board migration complete.

## Verification

Commands run:

```bash
cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings
cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2
cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings
```

Result:

- 31 `pickem_api` tests passed for Plan 04.
- 40 `pickem_homepage` tests passed for Plan 04.
- 71 full-suite tests passed for Plan 04.
- `makemigrations --check --dry-run` reported `No changes detected`.
- Django check reported 13 existing warnings for `max_length` on `IntegerField` fields in `userStats`.
- Phase 1 final plan check passed and confirmed prior blockers were resolved:
  - message-board-only legacy memberships covered;
  - research open questions resolved;
  - validation artifact added;
  - owner fallback and role-preservation tests/tasks included in Plan 02;
  - final verification moved to dependent Wave 3 Plan 04.
- Phase 2 verification passed:
  - `manage.py check --settings=pickem.test_settings` passed with 13 existing `userStats` warnings.
  - `makemigrations --check --dry-run --settings=pickem.test_settings` reported `No changes detected`.
  - 47 `pickem_api` tests passed.
  - 45 `pickem_homepage` tests passed.
  - 92 full-suite tests passed.
- Phase 3 Plan 02 verification passed:
  - `manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` passed with 58 tests.
  - `makemigrations --check --dry-run --settings=pickem.test_settings` reported `No changes detected`.
  - Both commands reported the 13 existing `pickem_api.userStats` `IntegerField(max_length=...)` warnings.
- Phase 3 Plan 03 verification passed:
  - `manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2` passed with 113 tests.
  - `manage.py check --settings=pickem.test_settings` passed with the 13 existing `pickem_api.userStats` `IntegerField(max_length=...)` warnings.
- Phase 3 Plan 04 verification passed:
  - `manage.py test pickem_homepage.tests.FamilySwitcherContextTests --settings=pickem.test_settings --verbosity=2` passed with 3 tests after implementation.
  - `manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` passed with 69 tests.
  - `curl -s --max-time 5 http://localhost:8000 | head -40` returned public homepage HTML.
- Phase 3 Plan 05 final verification passed:
  - `manage.py check --settings=pickem.test_settings` passed with the 13 existing `pickem_api.userStats` `IntegerField(max_length=...)` warnings.
  - `manage.py makemigrations --check --dry-run --settings=pickem.test_settings` reported `No changes detected`.
  - `manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2` passed with 116 tests.
  - `manage.py test --settings=pickem.test_settings --verbosity=2` passed with 116 tests.
  - `curl -s --max-time 5 http://localhost:8000 | head -40` returned public homepage HTML.

## Next Action

Proceed to Phase 4: plan/execute family-scoped app pages for dashboard/home, scores, standings, picks, rules, profiles, and message board. Do not execute Phase 4 until its GSD plan is selected.

## Session

**Last session:** 2026-06-29T13:41:30Z
**Stopped at:** Completed 03-05-PLAN.md
**Resume file:** None

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 03-onboarding-and-family-selection P01 | 201 | 3 tasks | 6 files |
| Phase 03-onboarding-and-family-selection P02 | 250 | 3 tasks | 6 files |
| Phase 03-onboarding-and-family-selection P03 | 346 | 3 tasks | 7 files |
| Phase 03-onboarding-and-family-selection P04 | 176 | 3 tasks | 4 files |
| Phase 03-onboarding-and-family-selection P05 | 130 | 3 tasks | 4 files |
