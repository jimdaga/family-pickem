# Test Plan: Family Multi-Tenancy

**Date:** 2026-06-28

## Baseline

Current tests are Django `TestCase` tests in:

- `pickem/pickem_api/tests.py`
- `pickem/pickem_homepage/tests.py`

Current CI command:

```bash
cd pickem && python manage.py test --settings=pickem.test_settings --verbosity=2
```

Current coverage is mostly model/serializer smoke tests and public page status checks. Multi-tenant work needs authorization-first tests before broad route migration.

## Unit Tests

Model tests:

- `Family` slug uniqueness and display behavior.
- `FamilyMembership` unique `(family, user)`.
- Role choices and helper predicates.
- `Pool` unique `(family, slug)`.
- `FamilyInvitation` code hashing, expiry, revocation, max-use behavior.
- `FamilyAuditLog` creation helpers.
- Tenant-scoped unique constraints for picks and standings.

Authorization helper tests:

- `resolve_family_or_404` allows active member.
- `resolve_family_or_404` denies non-member.
- `resolve_pool_or_404` denies pool from another family.
- `require_family_role` allows exact roles.
- Member denied admin/owner actions.
- Admin denied owner-only actions.

Input validation tests:

- Week number must be 1-18.
- Pick team must match game's home/away team.
- Tiebreaker values numeric and bounded.
- Invite code shape and expiry validation.
- Role changes cannot remove last owner.

## Integration Tests

Onboarding:

- New signed-in user with no membership redirects to onboarding.
- Create family creates owner membership and default pool.
- Join valid invite creates member membership.
- Expired/revoked invite returns safe error.

Family routes:

- One-family user lands in default pool dashboard.
- Multi-family user can switch families.
- Current family/pool context appears in template context.
- Legacy global routes redirect to selected/default family context.

Picks:

- Member can create a pick in own pool.
- POST with forged pool/family/user fields is rejected or ignored.
- Duplicate pick for same `(pool, user, game)` updates or rejects by defined policy.
- Locked game cannot be edited by member.
- Admin manual pick requires target user membership in same family.

Standings/scoring:

- Scoring pool A does not update pool B.
- Weekly winner for pool A does not clear pool B winner.
- Season standings filtered by pool.
- Footer stats filtered by current pool.

Message board:

- Family member can read/write own family board.
- Non-member cannot read posts/comments by ID.
- Votes cannot target another family.
- Counts remain correct after vote add/change/delete.

Admin:

- Member cannot access settings, invites, role management, or manual pick APIs.
- Admin can invite/remove members where allowed.
- Owner can transfer ownership or promote admin.
- Last owner cannot be removed/demoted.
- Audit rows are created for sensitive actions.

API:

- Every private API endpoint requires authentication.
- Every family/pool API endpoint requires membership.
- Cross-family IDs in URL/body are denied.
- Staff/global API behavior is explicitly defined and tested.

## E2E Tests

Add Playwright or Django LiveServer-based browser tests when the UI routes exist:

- Anonymous visitor -> Google sign-in substitute/mock -> onboarding.
- Create family -> dashboard -> submit picks -> standings.
- Owner invites member -> member joins -> member submits picks.
- User with two families switches context; header and URLs update.
- User A copies family B URL/API call and is denied.
- Mobile nav switcher works.

## Authorization Negative Tests

Minimum matrix per tenant-owned feature:

| Feature | Negative test |
|---|---|
| Dashboard | Non-member cannot view |
| Picks page | Non-member cannot view or submit |
| Pick edit | User cannot edit another user's pick |
| Pick submit | Forged `pool_id` does not write across families |
| Scores | Non-member cannot view family-specific pick overlays |
| Standings | Non-member cannot view |
| Profile | User cannot view another user's family-specific stats without shared family |
| Message board | Non-member cannot read/post/comment/vote |
| Invites | Member cannot create/revoke invites |
| Settings | Member cannot edit |
| Role management | Admin cannot remove last owner |
| Cron scoring | Pool B data unchanged after pool A job |

## Manual QA Checklist

New visitor:

- Landing page is public.
- Sign-in call to action is clear.

No-family signed-in user:

- Redirects to onboarding.
- Can create a family.
- Can join with invite.
- Empty states are clear.

Single-family user:

- Lands in family dashboard.
- Header shows current family/pool.
- Picks, scores, standings, rules, and profiles stay in context.

Multi-family user:

- Switcher is visible on desktop and mobile.
- Switching changes URL and context.
- Browser back/forward behaves sensibly.

Owner/admin:

- Invite create/revoke/regenerate.
- Member role changes.
- Settings updates.
- Unauthorized admin actions show clean errors.

Member:

- Can submit/edit allowed picks.
- Cannot see admin controls.
- Direct admin URLs denied server-side.

Security:

- Try changing slugs/IDs in URLs.
- Try POSTing another pool/family/user ID.
- Try fetching another family post/comment/pick.
- Confirm no raw stack traces or exception strings appear.

Migration:

- Legacy pool row counts match pre-migration counts.
- Default family standings match old global standings.
- Existing users can access default family.
- Non-member test user cannot access default family.

## Commands

```bash
cd pickem && python manage.py check --settings=pickem.test_settings
cd pickem && python manage.py test --settings=pickem.test_settings --verbosity=2
npm run build:prod
```
