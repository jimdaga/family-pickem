# Phase 1 Validation: Domain Schema Foundation

**Created:** 2026-06-28  
**Scope:** Schema, migrations, backfill, admin visibility, and focused tests for Phase 1 only. No application route, template, cron, onboarding, or authorization migration is validated here.

## Validation Dimensions

| Dimension | What Must Be Proven | Primary Evidence |
|---|---|---|
| Schema shape | `Family`, `FamilyMembership`, `Pool`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog` exist with safe constraints and indexes. | Model tests, generated migrations, `makemigrations --check --dry-run`. |
| Nullable-first migration safety | Pool/family FKs on legacy tables are nullable and no strict tenant uniqueness is enforced on legacy rows. | Migration inspection, model tests, dry-run migration check. |
| Legacy competition backfill | Existing picks, standings, retained user points, and stats receive the deterministic legacy pool without changing denormalized user fields. | `pickem_api` migration tests and row-count/null checks. |
| Legacy community backfill | Existing posts, comments, and votes receive the deterministic legacy family; existing banners remain site-wide with `family=None`. | `pickem_homepage` migration tests. |
| Membership mapping | Superusers become owners, non-superuser commissioners become admins, active competition users become members, and message-board-only active users become members. | Backfill helper tests covering API and homepage sources. |
| Secret handling | Invitations store `code_hash` only; no raw invite code field exists in models, admin, tests, or migrations. | Model/admin tests and source grep. |
| Admin visibility | Tenant domain and tenant FK fields are inspectable in Django admin without exposing invite secrets. | Admin registration tests and `manage.py check`. |

## Validation Architecture

1. Use Django `TestCase` tests in `pickem/pickem_api/tests.py` for core domain models, competition pool fields, competition backfill, owner/admin mapping, invite secrecy, and audit-log creation.
2. Use Django `TestCase` tests in `pickem/pickem_homepage/tests.py` for `SiteBanner.family`, message-board family fields, homepage backfill, and message-board-only membership creation.
3. Keep migration backfill logic testable by placing pure helper functions inside the migration files when direct migration-state tests would be too heavy for the current suite.
4. Use historical models via `apps.get_model` in migrations; tests must prove migration helpers do not import live models.
5. Run dry-run migration checks after generated migrations are committed so the repository has no ungenerated model changes.

## Edge Cases

- No active superuser exists: promote the first active commissioner to owner.
- No active superuser or active commissioner exists: promote the earliest active user referenced by competition or message-board activity to owner.
- A user has only message-board activity: create an active legacy `member` membership.
- A user already has an owner/admin membership: do not downgrade them when processing member activity.
- Denormalized competition references point to inactive, deleted, or unmatched users: skip without failing.
- Message-board rows reference inactive or no-longer-resolvable users: skip membership creation without failing while still backfilling family where the row exists.
- Existing `SiteBanner` rows: leave `family=None` so current site-wide behavior remains intact.
- Re-running backfill helpers: no duplicate family, pool, settings, or membership rows.

## Negative Tests And Backstops

- Assert `GamesAndScores`, `GameWeeks`, and `Teams` do not gain family or pool fields.
- Assert legacy pool/family FKs stay nullable in Phase 1.
- Assert no `UniqueConstraint` is added to legacy competition tables for tenant-scoped pick or standings uniqueness.
- Assert `FamilyInvitation` has no raw invite-code field and admin does not display one.
- Assert missing or inactive users do not abort backfill.
- Assert message-board-only active users are not omitted from legacy memberships.

## Commands

Run after each relevant plan:

```bash
cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings
cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings
cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings --verbosity=2
cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2
```

Run before Phase 1 is accepted:

```bash
cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2
```

## Release Criteria

- All Phase 1 PLAN verification commands pass or have documented pre-existing failures.
- Every tenant-owned legacy row has a nullable tenant assignment where applicable after backfill.
- Existing banner behavior is preserved with site-wide `family=None` rows.
- Membership coverage includes active users from competition data and message-board activity.
- No runtime route behavior, cron behavior, templates, or authorization rules are changed in Phase 1.
