# Roadmap: Family Pickem Multi-Tenancy

**Created:** 2026-06-28  
**Current focus:** Phase 1: Domain Schema Foundation

## Phase 0: Discovery And Repo Readiness

**Status:** Complete

Discovery artifacts:

- `DISCOVERY.md`
- `FAMILY_MULTI_TENANCY_PLAN.md`
- `SECURITY_THREAT_MODEL.md`
- `MIGRATION_PLAN.md`
- `TEST_PLAN.md`

Definition of done:

- Existing architecture, domain model, routes/APIs, security risks, UX gaps, and migration strategy documented.
- Existing checks/tests run.

## Phase 1: Domain Schema Foundation

**Goal:** Introduce the family/pool schema and safely attach existing global data to a default legacy family/pool without changing runtime behavior broadly.

**Plans:** 1/4 plans executed

Plans:

- [x] 01-01-PLAN.md — Create core family/pool/membership/invitation/audit schema.
- [ ] 01-02-PLAN.md — Add nullable pool scope and legacy competition data backfill.
- [ ] 01-03-PLAN.md — Add nullable family scope for homepage community and banner data.
- [ ] 01-04-PLAN.md — Run final Phase 1 verification after all implementation plans complete.

Scope:

- Add `Family`, `FamilyMembership`, `Pool`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog`.
- Add nullable tenant FKs to tenant-owned legacy tables.
- Add idempotent data migration for default legacy family/pool.
- Backfill picks, standings, stats, message board rows, and banners.
- Add admin registrations and focused model/migration tests.

Definition of done:

- Existing pages/tests still pass.
- Every existing tenant-owned row has a legacy family/pool assignment where applicable.
- New schema supports owner/admin/member roles and invite code lifecycle.
- No route migration is required yet.

## Phase 2: Authorization Foundation

**Goal:** Centralize family/pool resolution, role checks, and tenant-scoped query helpers before moving pages.

Scope:

- Add tenant authz helpers.
- Add reusable guards for family/pool pages and API endpoints.
- Add negative tests for non-member and wrong-role access.
- Define 404 vs 403 behavior.

Definition of done:

- New family/pool routes cannot be written without a shared guard.
- Cross-family helper tests pass.

## Phase 3: Onboarding And Family Selection

**Goal:** Let users create, join, and switch families/pools.

Scope:

- Post-login routing for zero/one/multiple family memberships.
- Create family flow.
- Join family by invite flow.
- Header/mobile family switcher.
- Empty states.

Definition of done:

- Signed-in users can get into an authorized family/pool context without seeing global league data.

## Phase 4: Family-Scoped App Pages

**Goal:** Move user-facing gameplay pages into explicit tenant context.

Scope:

- Dashboard/home, scores, standings, picks, rules, profiles, message board.
- Tenant-aware URLs and links.
- Tenant-scoped query filters for picks, standings, stats, and community content.
- Legacy route redirects.

Definition of done:

- Cross-family page/API access is denied.
- No global pick/standing/message data appears inside a family context.

## Phase 5: Family Admin Experience

**Goal:** Replace global commissioner behavior with family owner/admin management.

Scope:

- Family settings.
- Member management.
- Invite management.
- Role management.
- Audit log display.
- Tenant-scoped manual pick and week-winner admin actions.

Definition of done:

- Owners/admins can manage their family safely.
- Members cannot access admin actions by direct URL/API call.

## Phase 6: Production Migration And Hardening

**Goal:** Enforce tenant constraints and harden production operations.

Scope:

- Make tenant FKs non-null after route/write migration.
- Add tenant-scoped unique constraints and indexes.
- Convert or harden cron/scoring paths to pool-aware behavior.
- Add migration verification runbook.
- Harden settings, CSRF, rate limiting, secrets, and logging.

Definition of done:

- Production data has enforced tenant boundaries.
- Backup/rollback and verification procedures are documented and rehearsed.

## Phase 7: Polish And QA

**Goal:** Make the multi-family product feel native, clear, and trustworthy.

Scope:

- Copy pass from global league language to family/pool language.
- Mobile family switcher QA.
- Accessibility review.
- Error/empty/loading states.
- E2E happy path and cross-family isolation tests.

Definition of done:

- New visitor, no-family user, one-family user, multi-family user, owner/admin, and member journeys all pass manual QA.

## Current Recommendation

Start with Phase 1. Do not begin by changing routes or UI filters; schema and migration foundations must come first so every later route has a real tenant key to enforce.
