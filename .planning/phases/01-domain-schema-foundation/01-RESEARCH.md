# Phase 1: Domain Schema Foundation - Research

**Researched:** 2026-06-28  
**Domain:** Django 4.0 schema, migrations, and multi-tenant data backfill  
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- D-01: Separate `Family` from `Pool`; a family is the social/admin container, and a pool is the competition/scoring container.
- D-02: Phase 1 should support one default pool per family in practice while leaving the schema capable of multiple pools later.
- D-03: Use owner/admin/member membership roles at the family level.
- D-04: Include membership status so inactive/removed memberships can be represented without deleting historical rows.
- D-05: Include `PoolSettings` now, but keep settings minimal and conservative.
- D-06: Keep `GamesAndScores`, `GameWeeks`, and `Teams` as global NFL reference data in Phase 1.
- D-07: Do not duplicate NFL game/week/team rows per family.
- D-08: Picks and standings should gain explicit `pool` scope while continuing to reference global game identifiers during the transition.
- D-09: Create a default legacy family and pool idempotently in a data migration.
- D-10: Backfill existing `GamePicks`, `userSeasonPoints`, retained `userPoints`, `userStats`, message-board rows, and family-scoped banners where applicable.
- D-11: Add tenant foreign keys as nullable first, backfill them, and avoid enforcing non-null tenant constraints until later phases.
- D-12: Do not drop legacy denormalized user fields in this phase.
- D-13: Map existing `UserProfile.is_commissioner` users and superusers to owner/admin memberships for the legacy family.
- D-14: Create family memberships for active users referenced by existing picks, standings, stats, or message-board activity.
- D-15: Add `FamilyInvitation` with hashed invite codes, expiry, revocation, max uses, and use count.
- D-16: Do not store raw invite codes at rest.
- D-17: Add `FamilyAuditLog` to support later logging of role changes, invites, settings changes, manual picks, and winner overrides.
- D-18: Phase 1 may add model/admin/test support for audit logs, but detailed audit event wiring belongs to later admin/action phases.
- D-19: Preserve current application behavior as much as possible in Phase 1.
- D-20: Existing routes may continue using legacy/global assumptions until later phases, but new writes introduced in Phase 1 must include tenant keys where relevant.
- D-21: Avoid broad refactors of large view/template files during schema foundation.
- D-22: Add indexes/constraints that are safe before route migration; defer non-null enforcement and strict tenant-scoped uniqueness until data/write paths are migrated and duplicates are known.

### the agent's Discretion

- Exact Django app placement for new models, but prefer `pickem_api.models` for domain/competition schema and `pickem_homepage.models` only for community-owned rows if that better preserves current boundaries.
- Exact legacy family/pool names and slugs, provided they are deterministic and documented.
- Whether `SiteBanner.family` is nullable to preserve site-wide banners, provided the migration plan documents the choice.

### Deferred Ideas (OUT OF SCOPE)

- Onboarding create/join/switch UI.
- Tenant-aware page URLs and redirects.
- Full authorization helper migration.
- Scoped API route migration.
- Cron/scoring pool-aware implementation.
- Non-null tenant FK enforcement.
- Full standings normalization.
</user_constraints>

## Summary

Phase 1 should be an expand/backfill-only Django migration phase: add the family/pool domain tables, add nullable tenant FKs to tenant-owned rows, create a deterministic default legacy family/pool, and backfill existing rows without changing route behavior broadly. [VERIFIED: codebase grep] The existing schema has global `GamePicks`, `userSeasonPoints`, `userPoints`, and `userStats` rows in `pickem_api.models`, and global `SiteBanner` plus message-board rows in `pickem_homepage.models`. [VERIFIED: codebase grep]

Use `pickem_api.models` for `Family`, `FamilyMembership`, `Pool`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog`; then reference those models from `pickem_homepage` community models. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md] This follows the current app boundary where competition/domain data lives in `pickem_api` and message-board/banner data lives in `pickem_homepage`. [VERIFIED: codebase grep]

**Primary recommendation:** implement schema in two or three migrations per affected app: create domain tables, add nullable FKs, then run an idempotent `RunPython` backfill using historical models and verification tests. [CITED: https://docs.djangoproject.com/en/4.0/topics/migrations/]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Family identity and membership roles | Database / Storage | API / Backend | Durable role and status state belongs in normalized tables; later request guards read it server-side. [VERIFIED: .planning/REQUIREMENTS.md] |
| Pool competition boundary | Database / Storage | API / Backend | Picks, standings, and stats need a stable `pool_id` before route scoping can be enforced. [VERIFIED: FAMILY_MULTI_TENANCY_PLAN.md] |
| Legacy data backfill | Database / Storage | API / Backend | Existing global rows must receive tenant keys through migrations before runtime code can rely on them. [VERIFIED: MIGRATION_PLAN.md] |
| Invitations | Database / Storage | API / Backend | Invite metadata, hashed code, expiry, revocation, and use counts must be persisted; join flows are later. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md] |
| Audit logs | Database / Storage | API / Backend | Phase 1 provides append-only storage; later phases wire events from admin actions. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| Message-board tenancy | Database / Storage | Browser / Client | Posts/comments/votes are currently global and must carry or derive family context before UI route migration. [VERIFIED: codebase grep] |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEN-02 | A family has at least one pool for a season/competition. | Add `Pool(family, season, competition, status)` and create the default legacy pool in data migration. [VERIFIED: .planning/REQUIREMENTS.md] |
| TEN-03 | A signed-in user can belong to one or more families. | Add `FamilyMembership` with unique `(family, user)` and active/inactive status. [VERIFIED: TEST_PLAN.md] |
| TEN-04 | A family membership has a role of owner, admin, or member. | Use constrained role choices and model helpers for owner/admin/member predicates. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md] |
| TEN-05 | Existing global production data is assigned to a default legacy family and pool. | Add nullable tenant FKs and idempotent backfill for picks, standings, stats, community rows, and banners. [VERIFIED: MIGRATION_PLAN.md] |
| POOL-01 | Picks are scoped to a pool. | Add nullable `GamePicks.pool`; defer uniqueness and non-null enforcement. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| POOL-02 | Standings and weekly winners are scoped to a pool. | Add nullable `pool` to `userSeasonPoints` and retained `userPoints`. [VERIFIED: FAMILY_MULTI_TENANCY_PLAN.md] |
| COMM-01 | Message-board posts, comments, and votes are scoped to a family or pool. | Add `MessageBoardPost.family`, plus explicit `family` on comments/votes for query safety during migration. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| COMM-03 | Site/family banners do not leak across families. | Add nullable `SiteBanner.family` while preserving current site-wide banner behavior. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md] |
| SEC-01 | Security-sensitive admin actions are audit logged. | Add `FamilyAuditLog` table now; event wiring is deferred. [VERIFIED: SECURITY_THREAT_MODEL.md] |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- Do not start the dev server; assume it is already running at `http://localhost:8000`. [VERIFIED: AGENTS.md]
- Use `curl http://localhost:8000` to inspect rendered HTML when validating UI/CSS changes; Phase 1 has no UI change requirement. [VERIFIED: AGENTS.md]
- Run Django commands from `pickem` with the repo virtualenv, especially `python manage.py migrate`, `makemigrations`, `check`, and `test`. [VERIFIED: AGENTS.md]
- Use Django ORM rather than raw SQL for application code; migration verification SQL is acceptable as a runbook/check only. [VERIFIED: AGENTS.md]
- The project is mid Bootstrap-to-Tailwind migration; Phase 1 should avoid template/CSS changes. [VERIFIED: AGENTS.md]
- Required validation commands for Phase 1 planning are `makemigrations --check --dry-run`, `check`, and `test` with `pickem.test_settings`. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md]

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 4.0.2 | ORM models, migrations, constraints, admin, tests | Installed in the project virtualenv and pinned in `pickem/requirements.txt`. [VERIFIED: pip show] |
| django.contrib.auth User | Django 4.0.2 bundled | Membership user FK target | Current `UserProfile`, posts, comments, and votes already use `django.contrib.auth.models.User`. [VERIFIED: codebase grep] |
| Django migrations `RunPython` | Django 4.0.2 bundled | Idempotent data backfill | Official migrations docs support data migrations through `RunPython` and historical models. [CITED: https://docs.djangoproject.com/en/4.0/topics/migrations/] |
| Django model constraints/indexes | Django 4.0.2 bundled | Safe uniqueness/check/index enforcement | Official docs support `UniqueConstraint`, `CheckConstraint`, and `Meta.indexes`. [CITED: https://docs.djangoproject.com/en/4.0/ref/models/constraints/] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Django admin | Django 4.0.2 bundled | Inspect and manage new schema | Add admin registrations consistent with current `ModelAdmin` patterns. [VERIFIED: codebase grep] |
| Django test runner | Django 4.0.2 bundled | Model, migration, and system-check tests | Existing tests use `django.test.TestCase` and `pickem.test_settings`. [VERIFIED: codebase grep] |
| Python `secrets` and Django hash helpers | Python stdlib / Django bundled | Generate high-entropy raw invite codes and store hashes | Store only hashed invite codes per locked decision D-16. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct `FamilyMembership` only | Add `PoolMembership` now | Defer `PoolMembership`; v1 assumes family membership grants pool access, and the context explicitly allows one default pool per family. [VERIFIED: FAMILY_MULTI_TENANCY_PLAN.md] |
| Nullable FKs first | Immediate non-null tenant FKs | Immediate non-null can fail or lock on existing rows; locked decision D-11 defers enforcement. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md] |
| Explicit `family` on comments/votes | Derive through post/comment joins only | Explicit `family` duplicates data but improves query/index safety during migration and is recommended by the threat model. [VERIFIED: SECURITY_THREAT_MODEL.md] |

**Installation:** no external package installs are required. [VERIFIED: pip show]

## Package Legitimacy Audit

No external packages should be installed in Phase 1. [VERIFIED: .planning/ROADMAP.md]

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| none | PyPI | — | — | — | OK | No install required |

**Packages removed due to [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```text
Existing global rows
  |
  v
Schema migration: Family / Pool / Membership / Settings / Invitation / Audit tables
  |
  v
Nullable tenant FK migration
  |--> pickem_api: GamePicks, userSeasonPoints, userPoints, userStats
  |--> pickem_homepage: SiteBanner, MessageBoardPost, MessageBoardComment, MessageBoardVote
  |
  v
RunPython backfill using historical models
  |--> get_or_create legacy Family
  |--> get_or_create legacy Pool
  |--> derive memberships from active users and referenced activity
  |--> map superusers/UserProfile.is_commissioner to owner/admin
  |--> update existing tenant-owned rows
  |
  v
Verification
  |--> no unexpected null tenant FKs
  |--> row counts unchanged
  |--> duplicate candidates reported before strict constraints
  |--> existing pages/tests still pass
```

### Recommended Project Structure

```text
pickem/
├── pickem_api/
│   ├── models.py          # Family, membership, pool, settings, invitations, audit, pool FKs
│   ├── admin.py           # Domain admin registrations
│   ├── tests.py           # Domain model and migration tests
│   └── migrations/        # Create tables, add nullable FKs, backfill
└── pickem_homepage/
    ├── models.py          # Community/banner family FKs
    ├── admin.py           # Community admin list filters/search additions
    ├── tests.py           # Community/banner tenant model tests
    └── migrations/        # Add community/banner FKs and backfill if dependency order requires it
```

### Pattern 1: Additive Schema Then Backfill

**What:** Create new tables and nullable FKs before any data migration or runtime enforcement. [VERIFIED: MIGRATION_PLAN.md]  
**When to use:** Use for every tenant field in Phase 1. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md]  
**Example:**

```python
# Source: Django 4.0 migration docs and local model patterns.
pool = models.ForeignKey(
    "pickem_api.Pool",
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    related_name="game_picks",
)
```

### Pattern 2: Historical Model Data Migration

**What:** In migrations, use `apps.get_model()` rather than importing live model classes. [CITED: https://docs.djangoproject.com/en/4.0/topics/migrations/]  
**When to use:** Use for legacy family/pool creation and row backfill. [VERIFIED: MIGRATION_PLAN.md]  
**Example:**

```python
# Source: Django 4.0 migration docs.
def forwards(apps, schema_editor):
    Family = apps.get_model("pickem_api", "Family")
    Pool = apps.get_model("pickem_api", "Pool")
    legacy_family, _ = Family.objects.get_or_create(
        slug="legacy-family-league",
        defaults={"name": "Legacy Family League", "status": "active"},
    )
    Pool.objects.get_or_create(
        family=legacy_family,
        slug="legacy-pickem",
        defaults={"name": "Legacy Pick'em", "season": 2526, "competition": "nfl"},
    )
```

### Pattern 3: Defer Strict Tenant Uniqueness

**What:** Add safe uniqueness for new domain tables now, but defer strict uniqueness on legacy data tables until duplicates are audited. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md]  
**When to use:** Use `UniqueConstraint` now for `Family.slug`, `FamilyMembership(family, user)`, `Pool(family, slug)`, `PoolSettings(pool)`, and `FamilyInvitation.code_hash`; defer `GamePicks(pool, uid, pick_game_id)` and standings uniqueness. [VERIFIED: SECURITY_THREAT_MODEL.md]

### Anti-Patterns to Avoid

- **Non-null tenant FKs in first migration:** This contradicts D-11 and risks failing on existing production rows. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md]
- **Importing live models inside migrations:** Historical migrations must use historical models, not current imports. [CITED: https://docs.djangoproject.com/en/4.0/topics/migrations/]
- **Storing raw invite codes:** Locked decision D-16 forbids raw invite codes at rest. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md]
- **Route or template refactors in Phase 1:** Onboarding, switchers, scoped routes, and broad authz migration are deferred. [VERIFIED: .planning/ROADMAP.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema evolution | Custom SQL-only migration scripts | Django migrations and `RunPython` | Keeps migration graph, test DB setup, and deploy behavior consistent. [CITED: https://docs.djangoproject.com/en/4.0/topics/migrations/] |
| Membership uniqueness | Manual duplicate checks only | DB `UniqueConstraint(family, user)` | Prevents duplicate active rows at the persistence boundary. [CITED: https://docs.djangoproject.com/en/4.0/ref/models/constraints/] |
| Invite code secrecy | Reversible encoding or raw code storage | High-entropy raw code returned once; hash stored in `code_hash` | Raw invite codes are sensitive and must not persist. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| Backfill verification | Visual admin inspection only | Automated migration/model tests plus row-count/null checks | Production migration needs repeatable verification. [VERIFIED: MIGRATION_PLAN.md] |

**Key insight:** Phase 1 succeeds by making tenant state explicit and verifiable while leaving runtime behavior largely untouched. [VERIFIED: .planning/ROADMAP.md]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Existing DB rows in `GamePicks`, `userSeasonPoints`, retained `userPoints`, `userStats`, `SiteBanner`, `MessageBoardPost`, `MessageBoardComment`, and `MessageBoardVote` are global today. [VERIFIED: codebase grep] | Add nullable tenant FKs and backfill to default legacy family/pool. |
| Live service config | No Phase 1 tenant identifiers are stored in external UI-managed service config yet. [VERIFIED: DISCOVERY.md] | None for schema foundation; later deployment runbook should pause cron writes during production backfill. |
| OS-registered state | No OS-level registrations contain family/pool names because the schema does not exist yet. [VERIFIED: DISCOVERY.md] | None. |
| Secrets/env vars | `.env.app` contains app/database/OAuth settings; no family/pool secret names exist yet. [VERIFIED: AGENTS.md] | Do not introduce invite-code secrets; generate codes at runtime and store hashes only. |
| Build artifacts | Django migration files and SQLite test DB state are generated by normal Django commands. [VERIFIED: codebase grep] | Run migrations/check/tests; no artifact rename is needed. |

## Common Pitfalls

### Pitfall 1: Missing/deleted users during membership backfill

**What goes wrong:** Legacy rows may reference users by `uid`, `userID`, or `userEmail`, and referenced users may be inactive or deleted. [VERIFIED: MIGRATION_PLAN.md]  
**Why it happens:** Current `GamePicks`, standings, and stats store denormalized user fields instead of user FKs. [VERIFIED: codebase grep]  
**How to avoid:** Build memberships only for `auth.User` rows that can be matched and are active; report unmatched references in migration verification output or tests. [VERIFIED: MIGRATION_PLAN.md]  
**Warning signs:** Distinct legacy user IDs/emails exceed created legacy memberships. [VERIFIED: MIGRATION_PLAN.md]

### Pitfall 2: Over-enforcing uniqueness before duplicate audit

**What goes wrong:** Adding tenant-scoped unique constraints to picks/standings can fail if global data already contains duplicates. [VERIFIED: MIGRATION_PLAN.md]  
**Why it happens:** Existing models do not define uniqueness on `GamePicks(uid, pick_game_id)` or `userSeasonPoints(userID, gameseason)`. [VERIFIED: codebase grep]  
**How to avoid:** Add indexes now; defer strict legacy-table unique constraints until Phase 6 after duplicate checks. [VERIFIED: .planning/ROADMAP.md]  
**Warning signs:** Duplicate candidate queries return rows for future `(pool, uid, pick_game_id)` or `(pool, userID, gameseason)`. [VERIFIED: MIGRATION_PLAN.md]

### Pitfall 3: Cross-app migration dependency errors

**What goes wrong:** `pickem_homepage` migrations reference `pickem_api.Family` before that model migration is applied. [VERIFIED: codebase grep]  
**Why it happens:** Domain models and community models live in separate Django apps. [VERIFIED: codebase grep]  
**How to avoid:** Put new domain tables in `pickem_api`, then make homepage migrations depend on the exact `pickem_api` migration that creates `Family` and `Pool`. [VERIFIED: codebase grep]

## Code Examples

### Invite Hashing Shape

```python
# Source: locked decision D-16 and Django/Python standard primitives.
import hashlib
import secrets

def generate_invite_code():
    raw_code = secrets.token_urlsafe(32)
    code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    return raw_code, code_hash
```

### Safe Constraints Shape

```python
# Source: Django 4.0 model constraints docs.
class FamilyMembership(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["family", "user"],
                name="unique_family_membership_user",
            ),
        ]
```

### Homepage Model Tenant FK Shape

```python
# Source: local cross-app FK pattern and Phase 1 decisions.
family = models.ForeignKey(
    "pickem_api.Family",
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    related_name="message_board_posts",
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global single league rows | Explicit tenant boundary columns on user/community rows | Phase 1 planned for 2026-06-28 | Later phases can enforce server-side tenant filtering. [VERIFIED: .planning/ROADMAP.md] |
| Global commissioner boolean | Family role memberships | Phase 1 schema, later authz enforcement | Preserves legacy commissioner mapping while enabling least privilege later. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| Raw/global message board | Family-scoped posts/comments/votes | Phase 1 schema | Prevents future post/comment ID-only leaks after route migration. [VERIFIED: SECURITY_THREAT_MODEL.md] |

**Deprecated/outdated:**
- `UserProfile.is_commissioner` as the only admin boundary: keep for compatibility in Phase 1, but map it to family roles for the legacy family. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md]
- Global standings/picks without `pool_id`: keep readable during transition, but backfill `pool` now and enforce later. [VERIFIED: .planning/ROADMAP.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Use `hashlib.sha256` for invite code hashing rather than Django password hashers. [ASSUMED] | Code Examples | A slower keyed or password-style hash may be preferred before public invite joins; planner can gate final helper design. |
| A2 | Deterministic slug names `legacy-family-league` and `legacy-pickem` are acceptable. [ASSUMED] | Architecture Patterns | Product copy may prefer a different name; migration must document whatever is chosen. |

## Open Questions

1. **Should `SiteBanner.family` default to legacy family or remain nullable for site-wide banners?**
   - What we know: context allows nullable `SiteBanner.family` to preserve site-wide banners. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md]
   - What's unclear: whether current active banners should be treated as legacy-family-only or global announcements.
   - Recommendation: add nullable `family`; leave existing rows null in Phase 1 unless product explicitly wants legacy-family assignment.

2. **Should the first superuser become legacy family owner while commissioners become admins?**
   - What we know: D-13 maps commissioners and superusers to owner/admin memberships. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md]
   - What's unclear: exact owner/admin split.
   - Recommendation: make superusers owners and `UserProfile.is_commissioner=True` non-superusers admins; ensure at least one owner exists.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python virtualenv | Django management commands | yes | Python 3.10 environment observed through `../venv/bin/python` | Use system Python only if venv missing. [VERIFIED: pip show] |
| Django | Models/migrations/tests | yes | 4.0.2 | None. [VERIFIED: pip show] |
| SQLite test DB | `pickem.test_settings` tests | yes | in-memory SQLite configured | None for tests. [VERIFIED: codebase grep] |
| PostgreSQL | Production/dev DB migration target | not probed locally | configured by project docs | Use Django migration SQL review and production snapshot. [VERIFIED: AGENTS.md] |
| gsd graphify | Optional graph context | no | disabled | Use explicit discovery docs and source inspection. [VERIFIED: gsd-tools] |

**Missing dependencies with no fallback:**
- None blocking research. [VERIFIED: gsd-tools]

**Missing dependencies with fallback:**
- Graphify disabled; source and planning docs cover this phase. [VERIFIED: gsd-tools]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Django test runner, Django 4.0.2 [VERIFIED: pip show] |
| Config file | `pickem/pickem/test_settings.py` [VERIFIED: codebase grep] |
| Quick run command | `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` |
| Full suite command | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| TEN-02 | Legacy family has default pool | migration/model | `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings` | yes, extend existing `pickem_api/tests.py` |
| TEN-03 | User can have memberships | unit | same | yes, extend |
| TEN-04 | owner/admin/member choices and status work | unit | same | yes, extend |
| TEN-05 | Backfill assigns legacy rows | migration test | full suite | yes, extend |
| POOL-01 | `GamePicks.pool` nullable and backfilled | migration/model | full suite | yes, extend |
| POOL-02 | standings rows get `pool` | migration/model | full suite | yes, extend |
| COMM-01 | community rows get `family` | migration/model | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` | yes, extend existing `pickem_homepage/tests.py` |
| COMM-03 | banners preserve nullable/site-wide behavior | unit | same | yes, extend |
| SEC-01 | audit log rows can be created | unit | pickem_api test command | yes, extend |

### Sampling Rate

- **Per task commit:** `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings`
- **Per wave merge:** `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2`
- **Phase gate:** full suite green plus `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings`

### Wave 0 Gaps

- [ ] Add focused tests for `Family`, `FamilyMembership`, `Pool`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog` in `pickem/pickem_api/tests.py`. [VERIFIED: TEST_PLAN.md]
- [ ] Add homepage model tests for family-scoped banner/message-board fields in `pickem/pickem_homepage/tests.py`. [VERIFIED: TEST_PLAN.md]
- [ ] Add migration/backfill tests or a management-test equivalent that migrates from pre-backfill state and validates default legacy assignments. [VERIFIED: MIGRATION_PLAN.md]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Continue using Django auth/allauth; no auth flow change in Phase 1. [VERIFIED: AGENTS.md] |
| V3 Session Management | no | No session behavior changes in Phase 1. [VERIFIED: .planning/ROADMAP.md] |
| V4 Access Control | yes | Add durable membership roles and tenant keys; route enforcement comes Phase 2+. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| V5 Input Validation | yes | Constrain role/status/action choices and validate invite expiry/use state in model tests. [VERIFIED: TEST_PLAN.md] |
| V6 Cryptography | yes | Store invite code hashes, not raw codes. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md] |

### Known Threat Patterns for Django Multi-Tenancy

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| BOLA/IDOR by changing object IDs | Information Disclosure / Elevation of Privilege | Add explicit tenant keys now; enforce membership guards later. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| Invite code leakage | Information Disclosure | Store hash only and do not log raw code. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| Cross-family message-board leakage | Information Disclosure | Add `family` boundary to posts/comments/votes. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| Duplicate or stale role rows | Elevation of Privilege | Unique membership rows plus status field instead of deletion-only history. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md] |

## Recommended Implementation Sequence

1. Add `Family`, `FamilyMembership`, `Pool`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog` to `pickem_api.models`, with safe constraints for new tables only. [VERIFIED: .planning/ROADMAP.md]
2. Add nullable `pool` to `GamePicks`, `userSeasonPoints`, retained `userPoints`, and `userStats`. [VERIFIED: MIGRATION_PLAN.md]
3. Add nullable `family` to `SiteBanner`, `MessageBoardPost`, `MessageBoardComment`, and `MessageBoardVote`; use `PROTECT` for family references where deletion would orphan history. [VERIFIED: SECURITY_THREAT_MODEL.md]
4. Add admin registrations/list filters/search fields for new domain models and tenant columns without changing current views. [VERIFIED: codebase grep]
5. Add idempotent `RunPython` backfill: create legacy family/pool, derive memberships, map superusers to owners and commissioners to admins, backfill tenant FKs. [VERIFIED: MIGRATION_PLAN.md]
6. Add focused tests for model constraints, invite hashing lifecycle, audit-log creation, and backfill behavior. [VERIFIED: TEST_PLAN.md]
7. Run `makemigrations --check --dry-run`, `check`, and full tests with `pickem.test_settings`. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md]

## Sources

### Primary (HIGH confidence)

- `pickem/pickem_api/models.py` - current global domain models and denormalized user fields. [VERIFIED: codebase grep]
- `pickem/pickem_homepage/models.py` - current global banner and message-board models. [VERIFIED: codebase grep]
- `.planning/phases/01-domain-schema-foundation/01-CONTEXT.md` - locked Phase 1 decisions. [VERIFIED: codebase grep]
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `MIGRATION_PLAN.md`, `SECURITY_THREAT_MODEL.md`, `TEST_PLAN.md` - phase scope, migration, security, and test requirements. [VERIFIED: codebase grep]

### Secondary (MEDIUM confidence)

- Django 4.0 migrations docs - `RunPython`, historical models, migration staging. [CITED: https://docs.djangoproject.com/en/4.0/topics/migrations/]
- Django 4.0 constraints docs - `UniqueConstraint` and `CheckConstraint`. [CITED: https://docs.djangoproject.com/en/4.0/ref/models/constraints/]
- Django 4.0 indexes docs - `Meta.indexes`. [CITED: https://docs.djangoproject.com/en/4.0/ref/models/indexes/]

### Tertiary (LOW confidence)

- Invite hashing helper exact implementation using `hashlib.sha256`; acceptable shape but should be finalized during implementation. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from virtualenv, requirements, and codebase. [VERIFIED: pip show]
- Architecture: HIGH - locked by Phase 1 context and discovery artifacts. [VERIFIED: .planning/phases/01-domain-schema-foundation/01-CONTEXT.md]
- Pitfalls: HIGH - derived from current model fields and migration plan risks. [VERIFIED: codebase grep]

**Research date:** 2026-06-28  
**Valid until:** 2026-07-28
