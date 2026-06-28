---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-06-28T18:51:32Z"
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 4
  completed_plans: 3
  percent: 75
---

# GSD State

**Project:** Family Pickem Multi-Tenancy  
**Updated:** 2026-06-28 after Phase 1 Plan 03 execution

## Project Reference

See: `.planning/PROJECT.md`

**Core value:** Families can run private pick'em pools with strict server-enforced data isolation.  
**Current focus:** Phase 01 — domain-schema-foundation

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

## Verification

Commands run:

```bash
cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings
cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2
cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings
```

Result:

- 40 homepage tests passed for Plan 03.
- Django check reported 13 existing warnings for `max_length` on `IntegerField` fields in `userStats`.
- Phase 1 final plan check passed and confirmed prior blockers were resolved:
  - message-board-only legacy memberships covered;
  - research open questions resolved;
  - validation artifact added;
  - owner fallback and role-preservation tests/tasks included in Plan 02;
  - final verification moved to dependent Wave 3 Plan 04.

## Next Action

Continue Phase 1 with Plan 04:

```bash
$gsd-execute-phase 1
```
