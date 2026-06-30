# Phase 1: Domain Schema Foundation - Context

**Gathered:** 2026-06-28  
**Status:** Ready for planning  
**Source:** Approved discovery package and roadmap

<domain>
## Phase Boundary

Phase 1 introduces schema foundations for family/pool tenancy without broadly changing runtime behavior or migrating user-facing routes. The phase must add the core domain models, attach existing tenant-owned data to a default legacy family/pool through safe migrations, expose the schema in admin where useful, and add focused tests proving the schema and migration behavior.

The phase should not implement onboarding, family switcher UI, tenant-aware page routing, or full authorization migration. Those are later phases.
</domain>

<decisions>
## Implementation Decisions

### Tenant model

- D-01: Separate `Family` from `Pool`; a family is the social/admin container, and a pool is the competition/scoring container.
- D-02: Phase 1 should support one default pool per family in practice while leaving the schema capable of multiple pools later.
- D-03: Use owner/admin/member membership roles at the family level.
- D-04: Include membership status so inactive/removed memberships can be represented without deleting historical rows.
- D-05: Include `PoolSettings` now, but keep settings minimal and conservative.

### Global reference data

- D-06: Keep `GamesAndScores`, `GameWeeks`, and `Teams` as global NFL reference data in Phase 1.
- D-07: Do not duplicate NFL game/week/team rows per family.
- D-08: Picks and standings should gain explicit `pool` scope while continuing to reference global game identifiers during the transition.

### Legacy data migration

- D-09: Create a default legacy family and pool idempotently in a data migration.
- D-10: Backfill existing `GamePicks`, `userSeasonPoints`, retained `userPoints`, `userStats`, message-board rows, and family-scoped banners where applicable.
- D-11: Add tenant foreign keys as nullable first, backfill them, and avoid enforcing non-null tenant constraints until later phases.
- D-12: Do not drop legacy denormalized user fields in this phase.
- D-13: Map existing `UserProfile.is_commissioner` users and superusers to owner/admin memberships for the legacy family.
- D-14: Create family memberships for active users referenced by existing picks, standings, stats, or message-board activity.

### Invitations and audit

- D-15: Add `FamilyInvitation` with hashed invite codes, expiry, revocation, max uses, and use count.
- D-16: Do not store raw invite codes at rest.
- D-17: Add `FamilyAuditLog` to support later logging of role changes, invites, settings changes, manual picks, and winner overrides.
- D-18: Phase 1 may add model/admin/test support for audit logs, but detailed audit event wiring belongs to later admin/action phases.

### Safety and compatibility

- D-19: Preserve current application behavior as much as possible in Phase 1.
- D-20: Existing routes may continue using legacy/global assumptions until later phases, but new writes introduced in Phase 1 must include tenant keys where relevant.
- D-21: Avoid broad refactors of large view/template files during schema foundation.
- D-22: Add indexes/constraints that are safe before route migration; defer non-null enforcement and strict tenant-scoped uniqueness until data/write paths are migrated and duplicates are known.

### the agent's Discretion

- Exact Django app placement for new models, but prefer `pickem_api.models` for domain/competition schema and `pickem_homepage.models` only for community-owned rows if that better preserves current boundaries.
- Exact legacy family/pool names and slugs, provided they are deterministic and documented.
- Whether `SiteBanner.family` is nullable to preserve site-wide banners, provided the migration plan documents the choice.
</decisions>

<canonical_refs>
## Canonical References

Downstream agents MUST read these before planning or implementing.

### Project planning

- `.planning/PROJECT.md` — project context, constraints, and key decisions.
- `.planning/REQUIREMENTS.md` — v1 requirements and phase traceability.
- `.planning/ROADMAP.md` — phase scope and definition of done.
- `.planning/STATE.md` — current GSD state.

### Discovery package

- `DISCOVERY.md` — current architecture, routes, domain model, security findings, UX findings, migration risks.
- `FAMILY_MULTI_TENANCY_PLAN.md` — recommended data model, URL model, authorization model, onboarding model, milestones.
- `SECURITY_THREAT_MODEL.md` — assets, actors, trust boundaries, attack scenarios, mitigation requirements, test matrix.
- `MIGRATION_PLAN.md` — default legacy family strategy, migration steps, rollback, verification checks.
- `TEST_PLAN.md` — required test coverage and negative authorization matrix.

### Current code

- `pickem/pickem_api/models.py` — core domain models that need tenant schema extensions.
- `pickem/pickem_homepage/models.py` — message-board and banner models that need family/pool boundaries.
- `pickem/pickem_api/admin.py` — admin registration patterns for domain models.
- `pickem/pickem_homepage/admin.py` — admin registration patterns for community models.
- `pickem/pickem_api/tests.py` — existing model/serializer test style.
- `pickem/pickem_homepage/tests.py` — existing view/model/system-check test style.
- `pickem/pickem/test_settings.py` — test environment.
</canonical_refs>

<specifics>
## Specific Requirements For Phase 1 Planning

- Plans must include migrations and tests, not only model class changes.
- Plans must include production migration safety checks and rollback notes.
- Plans must avoid making existing tenant FKs non-null too early.
- Plans must explicitly address whether the legacy data migration handles missing/deleted users referenced by denormalized fields.
- Plans must include verification commands:
  - `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings` where applicable after migrations are committed, or explain why not.
  - `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings`
  - `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2`
- Plans must account for existing dirty worktree files and avoid touching unrelated user changes.
</specifics>

<deferred>
## Deferred Ideas

- Onboarding create/join/switch UI.
- Tenant-aware page URLs and redirects.
- Full authorization helper migration.
- Scoped API route migration.
- Cron/scoring pool-aware implementation.
- Non-null tenant FK enforcement.
- Full standings normalization.
</deferred>

---
*Phase: 01-domain-schema-foundation*  
*Context gathered: 2026-06-28 from approved discovery package*
