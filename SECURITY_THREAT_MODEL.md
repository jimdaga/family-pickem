# Security Threat Model: Family Multi-Tenancy

**Date:** 2026-06-28  
**Security posture:** Tenant isolation is non-negotiable.

## Assets

- Family membership lists and roles.
- Invite codes/links.
- User picks before and after lock time.
- Standings, weekly winners, bonuses, and scoring history.
- Family settings and pool rules.
- Message-board posts, comments, and votes.
- User profile data including phone number, favorite team, privacy setting, and OAuth-linked identity.
- Admin actions and audit trail.
- API tokens used by cron jobs.
- Production database and backups.

## Actors

- Anonymous visitor.
- Authenticated user with no family.
- Family member.
- Family admin.
- Family owner.
- Global Django superuser/staff.
- Background cron/scoring job.
- External attacker.
- Curious authenticated user trying to enumerate other families.

## Trust Boundaries

- Browser to Django server.
- Django templates/AJAX to server-side views.
- Public API consumers to DRF endpoints.
- Cron jobs to application/API/database.
- Django app to PostgreSQL.
- Django app to Google OAuth/allauth.
- Django app to ESPN APIs.
- App/deployment to secrets stores.
- Cache/precomputed data to request rendering.

## Attack Scenarios And Required Mitigations

| Scenario | Current risk | Required mitigation |
|---|---|---|
| User changes family or pool ID in URL | No tenant URLs yet; future BOLA risk | Resolve family/pool server-side and require active membership |
| User requests another user's picks | API exposes pick lists by game/season/week/user identifiers | Scope by pool and membership; only allow configured visibility |
| User posts to another family message board | Post/comment IDs are global | Store family on posts and require membership on every read/write |
| Member accesses admin tools | Commissioner is global today | Replace with family membership roles and per-action guards |
| User forges pick POST fields | Pick form exposes user/game/season/correctness fields | Server derives user, game, season, pool, and correctness; expose only allowed pick/tiebreaker inputs |
| Admin manually submits pick for user outside family | Current endpoint accepts `user_id` and `game_id` | Verify admin role, target user's membership, game validity, pool status, and lock/admin override policy |
| Cache leaks standings across families | Future cache keys could be global | Include `family_id`/`pool_id` in every cache key and invalidation path |
| Invite code brute force | No invite model yet | High-entropy codes, hash at rest, expiry, revocation, max uses, rate limiting |
| Invite code leakage in logs | Future risk | Never log raw code; redact query strings where possible |
| Cross-site request on JSON endpoint | Some endpoints use `@csrf_exempt` | Remove exemptions or require token auth with CSRF-safe design |
| XSS through message board/profile text | Django templates escape by default, but rich text not present | Keep escaping, validate lengths, avoid marking user content safe |
| Error response reveals existence | Raw exceptions and specific 404s | Return stable generic errors; log details server-side |
| Debug or secrets exposure | `DEBUG='True'`, older deps, secret manifests | Harden settings, secret scanning, dependency review, production checks |

## Tenant Isolation Risks

Every tenant-owned table must carry or derive an explicit tenant boundary:

- Direct `pool_id`: `GamePicks`, `userSeasonPoints`, future weekly result/stat rows.
- Direct `family_id`: `FamilyMembership`, `FamilyInvitation`, `FamilyAuditLog`, message-board posts, family settings.
- Indirect through parent with careful joins: comments/votes can inherit from posts, but explicit family can improve constraints and query safety.

Do not rely on:

- Hidden form fields.
- URL slug alone.
- Client-provided `family_id`/`pool_id`.
- Filtering only by user email.
- UI hiding admin buttons.
- Public API read endpoints for private data.

## Required Mitigations

- Central tenant resolution helpers.
- Central role guards.
- Query helper or manager patterns for family/pool scoping.
- Server-derived writes for picks and admin actions.
- Tenant-scoped unique constraints:
  - `FamilyMembership(family, user)`.
  - `Pool(family, slug)`.
  - `GamePicks(pool, uid, pick_game_id)`.
  - `userSeasonPoints(pool, userID)` or better user FK.
- Tenant-scoped indexes for hot views.
- CSRF protection on session-authenticated JSON endpoints.
- Input validation for week numbers, user IDs, game IDs, invite codes, role changes, and tiebreakers.
- Audit logging for invites, role changes, member removals, settings changes, manual picks, and winner overrides.
- Rate limiting for invites, onboarding joins, message posting, voting, and auth-adjacent endpoints.
- Production-safe settings (`DEBUG=False`, secure cookies, strict allowed hosts/origins).
- Negative tests for every tenant-scoped route/API.

## Security Test Matrix

| Test | Expected result |
|---|---|
| Anonymous visits family dashboard | Redirect to login or 404 |
| Authenticated non-member visits family dashboard | 404 or generic denial |
| Member of family A visits family B standings | Denied, no B data |
| Member of family A requests family B picks API | Denied |
| Member submits pick with forged pool ID | Pick saved only to resolved pool or request rejected |
| Member submits pick for another user | Rejected |
| Member accesses family settings | 403 |
| Admin manages settings in own family | Allowed |
| Admin manages settings in another family | Denied |
| Admin changes owner-only role | Denied |
| Owner revokes invite | Allowed and audit logged |
| Revoked invite is used | Denied |
| Expired invite is used | Denied |
| Invite join is brute forced repeatedly | Rate limited |
| Message-board post ID from another family is fetched | Denied |
| Comment created against post in another family | Denied |
| Vote submitted against another family content | Denied |
| Score cron updates pool A | Pool B standings unchanged |
| Cache for pool A standings requested in pool B | No cross-pool data |
| Raw database object ID in URL is changed | No unauthorized object returned |
| CSRF token omitted from session JSON mutation | 403 |
