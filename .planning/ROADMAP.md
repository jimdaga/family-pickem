# Roadmap: Family Pickem Multi-Tenancy

**Created:** 2026-06-28  
**Current focus:** Phase 4: Family-Scoped App Pages

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

**Plans:** 4/4 plans complete

Plans:

- [x] 01-01-PLAN.md — Create core family/pool/membership/invitation/audit schema.
- [x] 01-02-PLAN.md — Add nullable pool scope and legacy competition data backfill.
- [x] 01-03-PLAN.md — Add nullable family scope for homepage community and banner data.
- [x] 01-04-PLAN.md — Run final Phase 1 verification after all implementation plans complete. (completed 2026-06-28)

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

**Plans:** 3/3 plans complete

Plans:

- [x] 02-01-PLAN.md — Create core tenant authorization helpers.
- [x] 02-02-PLAN.md — Add view/API guards and a proof integration.
- [x] 02-03-PLAN.md — Run final Phase 2 verification and handoff. (completed 2026-06-28)

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

**Plans:** 5/5 plans complete

Plans:

- [x] 03-01-PLAN.md — Add post-login routing and onboarding shell.
- [x] 03-02-PLAN.md — Add create-family flow with default pool.
- [x] 03-03-PLAN.md — Add minimal invite creation and acceptance.
- [x] 03-04-PLAN.md — Add header/mobile family switcher.
- [x] 03-05-PLAN.md — Run final Phase 3 verification and handoff. (completed 2026-06-29)

Scope:

- Post-login routing for zero/one/multiple family memberships.
- Create family flow.
- Join family by invite flow.
- Header/mobile family switcher.
- Empty states.

Definition of done:

- Signed-in users can get into an authorized family/pool context without seeing global league data.

Completion evidence:

- Final summary: `.planning/phases/03-onboarding-and-family-selection/03-05-SUMMARY.md`.
- Django check, migration dry-run, focused `pickem_homepage pickem_api` tests, full test suite, and local public-home curl spot-check passed.
- Remaining global gameplay page migration is explicitly handed off to Phase 4.

## Phase 4: Family-Scoped App Pages

**Goal:** Move user-facing gameplay pages into explicit tenant context.

**Plans:** 6/6 plans complete

Plans:

- [x] 04-01-PLAN.md — Migrate dashboard/home into tenant context.
- [x] 04-02-PLAN.md — Move pick submit/edit into tenant URLs with server-derived writes.
- [x] 04-03-PLAN.md — Scope scores, standings, weekly winners, and rules.
- [x] 04-04-PLAN.md — Make profiles, player lists, and message-board AJAX family-private.
- [x] 04-05-PLAN.md — Clean shared navigation, shared context processors, dashboard, picks, and scores links.
- [x] 04-06-PLAN.md — Complete final link cleanup, negative tests, and validation handoff.

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

**Plans:** 2/7 plans executed

Plans:

- [x] 05-01-PLAN.md — Create tenant admin hub, scoped audit display, and admin navigation.
- [x] 05-02-PLAN.md — Add family, pool, rules/settings editing, and banner non-leakage preservation.
- [ ] 05-03-PLAN.md — Add member role/status management with owner protections.
- [ ] 05-04-PLAN.md — Add simple current-model invite management.
- [ ] 05-05-PLAN.md — Add tenant-scoped manual pick and user-pick retrieval tools.
- [ ] 05-06-PLAN.md — Add week-winner tools and disable legacy commissioner routes.
- [ ] 05-07-PLAN.md — Complete final cross-feature validation and handoff.

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

Proceed to Phase 5: replace global commissioner behavior with family owner/admin management. Phase 4 completed tenant-scoped user-facing gameplay pages and cross-family negative coverage, but family admin editing, cron/scoring hardening, and production migration hardening remain later-phase work.
