# Family Multi-Tenancy Plan

**Date:** 2026-06-28  
**Goal:** Add first-class families/pools with strict tenant isolation and a professional onboarding/admin experience.

## Recommended Product Model

Separate `Family` from `Pool`.

Rationale:

- A family is the social/admin container: members, roles, invites, settings, message board, audit log.
- A pool is the competition container: season, rules, picks, standings, scoring, weekly results.
- The first UI can create exactly one default pool per family, but the schema will not block future multiple pools, archives, alternate rules, or playoff pools.

Recommended models:

- `Family`
  - `id`, `name`, `slug`, `created_by`, timestamps, status fields.
  - Unique slug.
- `FamilyMembership`
  - `family`, `user`, `role`, `status`, timestamps.
  - Roles: `owner`, `admin`, `member`.
  - Unique `(family, user)`.
- `Pool`
  - `family`, `name`, `slug`, `season`, `competition`, `status`, timestamps.
  - Unique `(family, slug)`.
- `PoolSettings`
  - `pool`, scoring settings, visibility, pick deadline behavior, tiebreaker settings.
- `FamilyInvitation`
  - `family`, optional `pool`, `code_hash`, `created_by`, `role_to_grant`, expiry, max uses, use count, revoked timestamp.
  - Store hashes, not raw invite codes.
- `PoolMembership` optional
  - Only needed if a family member may belong to a family but not a specific pool.
  - If every family member participates in all pools for v1, defer this and use `FamilyMembership`.
- `FamilyAuditLog`
  - `family`, optional `pool`, `actor`, `action`, `target_type`, `target_id`, metadata JSON, timestamp, request IP/user agent if available.
- Tenant-scoped extensions:
  - `GamePicks.pool` or equivalent required tenant key.
  - `userSeasonPoints.pool`.
  - `userStats.pool` or replace with a pool-scoped stats model.
  - `MessageBoardPost.family` and possibly `pool`.
  - `MessageBoardComment` inherits through post but may also store `family` for simpler constraints/querying.
  - `MessageBoardVote` tenant reachable through post/comment; consider explicit `family` for query efficiency.
  - `SiteBanner.family` nullable if site-wide banners remain supported.

Global reference data:

- Keep `GamesAndScores`, `GameWeeks`, and `Teams` global NFL reference data keyed by season/week/competition.
- Do not duplicate NFL game rows per family unless families eventually need custom schedules.
- Picks and standings should reference global games plus pool/family context.

## Recommended URL Model

Use explicit tenant context in app URLs:

```text
/families/<family_slug>/
/families/<family_slug>/pools/<pool_slug>/
/families/<family_slug>/pools/<pool_slug>/picks/
/families/<family_slug>/pools/<pool_slug>/scores/
/families/<family_slug>/pools/<pool_slug>/standings/
/families/<family_slug>/rules/
/families/<family_slug>/members/
/families/<family_slug>/settings/
/families/<family_slug>/invites/
```

Compatibility strategy:

- Keep `/` as public landing page for unauthenticated users.
- After sign-in:
  - zero memberships -> onboarding.
  - one active pool -> redirect to that pool dashboard.
  - multiple memberships/pools -> redirect to last selected family/pool or chooser.
- Preserve legacy routes temporarily by redirecting authenticated users to their active/default pool.
- Avoid relying only on session-selected family. Use both URL context and server-side membership checks.

## Recommended Authorization Model

Centralize tenant authorization before migrating routes:

- `resolve_family_or_404(request, family_slug)`: returns only if user is an active member.
- `resolve_pool_or_404(request, family_slug, pool_slug)`: returns only if pool belongs to family and user is a member.
- `require_family_role(family, user, roles)`: owner/admin/member checks.
- `require_pool_access(pool, user)`: participation/visibility check.
- Query helpers:
  - `family_queryset(model, family)`
  - `pool_queryset(model, pool)`
  - `user_pool_picks(pool, user)`
- Admin guards:
  - owner: can delete family, transfer ownership, manage owners.
  - admin: can manage invites/settings/members except owner actions.
  - member: can submit picks and view allowed family/pool data.

Rules:

- Never trust `family_id`, `pool_id`, `user_id`, `game_id`, season, or week from the client without resolving against membership and allowed objects.
- Use 404 for inaccessible family/pool objects where practical to reduce existence leakage.
- Use 403 for authenticated users who are in the family but lack a role for an action.
- Scope cache keys, precomputed standings, and cron/scoring updates by `pool_id`.

## Recommended Onboarding UX

New unauthenticated visitor:

- Sees public landing page and signs in with Google.

Signed-in user with no family:

- Redirect to `/onboarding/`.
- Show two primary choices: create a family, join with invite code.
- Explain briefly that family pools are private.

Signed-in user with one family and one active pool:

- Redirect to `/families/<family_slug>/pools/<pool_slug>/`.

Signed-in user with multiple families/pools:

- Header shows current family/pool and a switcher.
- Switcher lists memberships and recent pools.
- Persist last active family/pool in session or profile, but still authorize every request.

Owner/admin:

- Invite members by link/code.
- Revoke/regenerate invites.
- Manage members and roles.
- Edit family/pool settings.
- View audit log for sensitive actions if feasible.

Member:

- Make picks, view scores/standings/rules/message board within current family/pool.
- No hidden-only admin controls; server returns 403/404 for unauthorized admin routes.

## Milestones

### Milestone 0: Repo Readiness And Baseline Discovery

Scope:

- Commit discovery docs.
- Confirm baseline test/build commands.
- Add or update project instructions if needed.
- Add baseline authorization/security test scaffolding only if necessary before schema work.

Likely files:

- `DISCOVERY.md`, `FAMILY_MULTI_TENANCY_PLAN.md`, `SECURITY_THREAT_MODEL.md`, `MIGRATION_PLAN.md`, `TEST_PLAN.md`
- Optional `.planning/*` docs.

Database migrations:

- None.

Security considerations:

- Do not change runtime behavior.
- Document current public/global surfaces.

Tests:

- Run current Django tests and system check.

Manual QA:

- Confirm current pages still load.

Rollback:

- Revert docs only.

Definition of done:

- Docs reviewed and first implementation milestone selected.

### Milestone 1: Domain Schema Foundation

Scope:

- Add `Family`, `FamilyMembership`, `Pool`, `PoolSettings`, `FamilyInvitation`, `FamilyAuditLog`.
- Add nullable `pool`/`family` fields to tenant-owned models.
- Create default legacy family and pool in a data migration.
- Backfill existing picks, standings, stats, message board rows, and banners.
- Add indexes and constraints that are safe at this stage.

Likely files:

- `pickem/pickem_api/models.py`
- `pickem/pickem_homepage/models.py`
- migrations in both apps
- admin registrations
- focused model tests

Database migrations:

- Add new tables.
- Add nullable tenant FKs.
- Backfill rows.
- Add unique constraints where duplicates are understood.

Security considerations:

- No route trusts the new fields yet.
- Migration must not expose partial tenant state.

Tests:

- Model creation.
- Default legacy family/pool migration.
- Membership uniqueness.
- Invite code hashing behavior.

Manual QA:

- Inspect admin.
- Verify all old pages still render against legacy pool fallback.

Rollback:

- Keep old fields intact.
- Migration should be reversible up to data backfill where feasible; production rollback relies on database snapshot.

Definition of done:

- Existing behavior still works and all legacy data has a tenant boundary column populated.

### Milestone 2: Authorization Foundation

Scope:

- Add tenant resolution helpers and role guards.
- Add tenant-scoped query helpers.
- Add tests proving positive and negative family access.
- Start refusing unscoped access in new helpers, while legacy routes still use fallback.

Likely files:

- `pickem/pickem_homepage/authz.py` or `services/tenant.py`
- `pickem/pickem_api/permissions.py`
- new tests in both apps

Database migrations:

- Possibly add missing indexes for membership lookups.

Security considerations:

- Membership checks server-side for every new family route.
- Avoid object existence leaks in helper behavior.

Tests:

- User A cannot resolve family B.
- Member cannot admin.
- Admin cannot owner-only.
- Non-member gets 404/403 as designed.

Manual QA:

- Verify owner/admin/member route behavior with dev data.

Rollback:

- Helpers are additive until routes migrate.

Definition of done:

- No new family-scoped route or API can be written without using a shared guard.

### Milestone 3: Onboarding And Family Selection

Scope:

- Add onboarding after login.
- Add create family and join-by-invite flows.
- Add family/pool switcher and current-context display.
- Persist last selected context.

Likely files:

- `pickem_homepage/views.py` or split onboarding/family views
- `pickem_homepage/urls.py`
- templates for onboarding/switcher/settings shell
- base template/context processor

Database migrations:

- None expected after Milestone 1.

Security considerations:

- Invite validation must use hashed codes and expiry/revocation checks.
- Joining must be idempotent and avoid revealing invalid vs unauthorized details beyond UX needs.

Tests:

- New user redirected to onboarding.
- Create family creates owner membership and default pool.
- Invite join creates member membership.
- Revoked/expired invite denied.

Manual QA:

- Google-login redirect flow.
- Mobile family switcher.
- Empty states.

Rollback:

- Feature-flag onboarding redirect if needed.

Definition of done:

- Signed-in users can create/join/select a family without seeing global league data.

### Milestone 4: Family-Scoped App Pages

Scope:

- Move dashboard/home, picks, scores, standings, rules, players/profiles into family/pool URLs.
- Ensure links preserve family/pool context.
- Remove global standings/picks leaks.
- Keep public marketing page separate.

Likely files:

- `pickem_homepage/urls.py`, `views.py` or split view modules
- `templates/pickem/base.html`, `home.html`, `picks.html`, `scores.html`, `standings.html`, `rules.html`, profile templates
- context processors and template tags

Database migrations:

- Consider making tenant FK non-null after all reads/writes are migrated and verified.

Security considerations:

- Every query for picks/standings/stats/message board must include `pool` or `family`.
- Public profile visibility should require shared family context.

Tests:

- Cross-family negative tests for every page.
- Forged pick POST cannot write to another family/pool.
- URLs with another family slug return 404/403.

Manual QA:

- One-family and multi-family journeys.
- Week navigation.
- Historical scores/standings.
- Mobile nav.

Rollback:

- Keep legacy redirects until confidence is high.

Definition of done:

- App pages are tenant-scoped and no global pick/standing/message data appears inside a family context.

### Milestone 5: Family Admin Experience

Scope:

- Family settings.
- Member and role management.
- Invite management.
- Audit log display if feasible.
- Convert commissioner tools from global to family roles.

Likely files:

- family admin views/templates/forms
- membership/invitation models/admin/tests
- audit logging helpers

Database migrations:

- Add audit metadata fields if needed.

Security considerations:

- Least privilege role checks.
- Owner-only safeguards.
- Audit sensitive actions.

Tests:

- Member cannot access admin pages/actions.
- Admin cannot remove last owner.
- Invite revoke/regenerate works.
- Audit rows created.

Manual QA:

- Member promotion/demotion/removal.
- Invite code lifecycle.

Rollback:

- Disable admin URLs while retaining data.

Definition of done:

- Family owners/admins can manage a pool without global commissioner access.

### Milestone 6: Data Migration And Production Hardening

Scope:

- Finalize non-null tenant constraints.
- Convert cron jobs to tenant-aware scoring.
- Add backup/rollback runbook.
- Add observability/security settings improvements.
- Enable rate limits where appropriate.

Likely files:

- migrations
- cron scripts or new management commands
- settings/deployment manifests
- docs/runbooks

Database migrations:

- Make tenant FKs non-null.
- Add unique constraints such as `(pool, uid, pick_game_id)`.
- Add indexes for hot tenant queries.

Security considerations:

- Production deploy order must prevent unscoped writes.
- Cache/precompute keys include pool/family.
- Secrets and debug settings hardened.

Tests:

- Migration verification tests where feasible.
- Tenant-aware scoring tests.
- API permission tests.

Manual QA:

- Staging migration rehearsal from production snapshot.
- Compare legacy and new standings for default pool.

Rollback:

- Snapshot restore or roll-forward fix; not just Django reverse migration.

Definition of done:

- Production data has enforced tenant boundaries and scoring jobs are tenant-aware.

### Milestone 7: Polish And QA

Scope:

- UX copy pass.
- Responsive/mobile review.
- Accessibility review.
- Error and empty states.
- End-to-end happy path and cross-family isolation tests.

Likely files:

- templates/static CSS
- E2E tests if introduced
- docs

Database migrations:

- None expected.

Security considerations:

- Verify no UI polish reintroduces hidden-control authorization assumptions.

Tests:

- E2E create family, invite member, submit picks, view standings.
- E2E user A cannot access family B pages/APIs.

Manual QA:

- New visitor, new user, existing one-family user, multi-family user, admin, member.

Rollback:

- Revert UI-only changes independently.

Definition of done:

- The product feels tenant-native rather than a global league with patched filters.

## Risks And Tradeoffs

- Separating `Family` and `Pool` is slightly more work now but prevents a likely future schema break.
- Keeping games/weeks/teams global is simpler and efficient, but all user-specific data must reference pool explicitly.
- Existing denormalized standings fields can remain initially, but long-term normalized weekly results would make multi-pool scoring safer.
- Public API reads are convenient for cron and debugging but incompatible with private family pools.
- Cron scripts calling HTTP endpoints will become fragile as authorization tightens; management commands are safer long term.

## Open Questions

- Should family message boards be per-family or per-pool in v1?
- Should a family member automatically participate in every pool?
- Should family owners be allowed to make a pool publicly viewable?
- How should existing global commissioners map: owner of legacy family or admin?
- Are custom family rules needed in v1, or can rules be shared copy/settings only?
