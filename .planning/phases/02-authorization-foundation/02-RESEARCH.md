# Phase 02 Research: Authorization Foundation

## Executive Summary

Phase 1 introduced `Family`, `Pool`, `FamilyMembership`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog`, plus nullable tenant scope on picks, standings, stats, and homepage community rows. Phase 2 should now add a centralized authorization foundation without migrating every page/API route.

The safest implementation shape is a small helper module in `pickem_api` that resolves active family membership, validates pool-to-family consistency, exposes role predicates, and raises predictable denial exceptions. Thin view/DRF adapters should convert those helper results into the locked UX/API behavior:

- anonymous browser/page access redirects to login;
- anonymous API/helper access raises an authentication error;
- authenticated non-members get 404 to reduce family existence leakage;
- active members without a sufficient role get 403;
- superusers and legacy commissioners do not bypass tenant helpers.

Broad tenant filtering of dashboard, picks, standings, scores, profiles, message board, and commissioner pages remains Phase 4/5 work. Phase 2 should include a tiny proof route/API endpoint or direct helper integration tests only, so later phases cannot accidentally invent one-off authorization behavior.

## Current Code Findings

`pickem/pickem_api/models.py` already has the Phase 1 domain objects:

- `Family` with `slug`, `status`, and active/inactive lifecycle.
- `Pool` with `family`, `slug`, `season`, `competition`, `status`, and `is_default`.
- `FamilyMembership` with family-level `owner`, `admin`, and `member` roles plus active/inactive status.
- `FamilyInvitation` and `FamilyAuditLog` for later onboarding/admin phases.
- `GamePicks`, `userSeasonPoints`, `userPoints`, and `userStats` now have nullable `pool`.

Homepage/community scope exists in `pickem_homepage.models` from Phase 1 for `SiteBanner`, `MessageBoardPost`, `MessageBoardComment`, and `MessageBoardVote`.

Current app behavior still assumes one global league:

- `pickem_homepage.views.index` reads `userSeasonPoints`, `GamePicks`, users, and message posts without family/pool filters.
- `standings`, `scores`, `submit_game_picks`, `edit_game_pick`, `user_profile`, and commissioner views still operate globally or by user/email/game only.
- message board AJAX handlers create/read/vote by post/comment IDs without membership checks.
- `pickem_api.views` exposes DRF function views such as global picks, user points, games, weeks, teams, and active games using broad querysets.

Existing global commissioner authorization is in `pickem_homepage.views.is_commissioner` and `commissioner_required`. It grants access to `is_superuser` or `UserProfile.is_commissioner`. Phase 2 tenant helpers must not reuse this for family authorization because the locked decision requires explicit active `FamilyMembership` even for superusers/commissioners.

`pickem_api.permissions.IsAdminOrReadOnly` only distinguishes safe methods from staff mutation. It does not understand tenant context and should not be expanded into family logic directly; add new tenant-aware DRF permission/adapters instead.

Existing tests are concentrated in `pickem_api/tests.py` and `pickem_homepage/tests.py`. Phase 1 tests already create families, pools, memberships, and legacy backfill data, so Phase 2 can build focused helper and view tests without needing new factories first.

## Recommended Implementation Shape

Add a new module `pickem/pickem_api/authz.py` as the canonical tenant authorization surface.

Recommended primitives:

- constants for role order: `member < admin < owner`;
- exception classes or dataclass result types for `AuthenticationRequired`, `TenantNotFound`, and `TenantPermissionDenied`;
- `get_active_membership(user, family)` returning an active membership or raising the appropriate denial;
- `require_family_membership(user, family_or_slug, minimum_role='member')`;
- `require_pool_membership(user, pool_or_slug, family=None, minimum_role='member')`;
- `resolve_family_by_slug(slug)` and `resolve_pool_in_family(family, pool_slug)`;
- `get_user_family_memberships(user)` for later onboarding/switcher work;
- `get_legacy_default_pool()` and `resolve_pool_context(..., allow_legacy_default=True)` as a temporary bridge for legacy global routes.

Add thin adapters rather than scattering status-code logic:

- `pickem_homepage/tenant_views.py` or `pickem_homepage/authz.py` with decorators/mixins such as `family_member_required` and `family_role_required`;
- DRF helpers/permissions in `pickem_api/permissions.py`, for example `FamilyScopedPermission` or explicit helper functions usable from function-based API views.

Keep the helper layer side-effect free. Audit logging belongs to future admin actions; Phase 2 can define where it will attach but should not emit audit rows for read checks.

## Security Findings

Primary current risk is IDOR/BOLA once tenant URLs or payloads exist. Many functions read by bare IDs (`post_id`, `comment_id`, `pick_id`, `user_id`, `game_id`) or broad season/week filters. Without shared helper enforcement, users could infer or manipulate another family’s data by changing route params, query params, or JSON bodies.

Specific risks to design against:

- inactive memberships must not authorize;
- non-members should receive 404, not 403, to avoid exposing family/pool existence;
- role failures for active members should be 403;
- `Pool` must be confirmed to belong to the supplied `Family`;
- superusers and global commissioners must not bypass tenant helper checks;
- tenant-scoped cache keys and memoized standings must include family/pool in later phases;
- `csrf_exempt` exists on some POST routes and should not spread to new tenant proof routes;
- API error bodies should avoid naming inaccessible families/pools.

## Test Strategy

Add focused tests before helper implementation:

- active member can resolve family/pool as `member`;
- admin and owner satisfy member/admin checks;
- member fails owner/admin checks with permission-denied behavior;
- inactive member is treated as non-member;
- authenticated non-member gets not-found behavior;
- anonymous helper/API access gets auth-required behavior;
- superuser without active membership is denied;
- `UserProfile.is_commissioner=True` without active membership is denied;
- user in family A cannot resolve/read family B pool;
- pool-family mismatch is denied/not found;
- legacy default fallback resolves only when explicitly allowed.

Test files can initially stay in existing modules:

- `pickem/pickem_api/tests.py` for unit-level helper tests;
- `pickem/pickem_homepage/tests.py` for page/decorator/proof-route behavior;
- API proof tests can also live in `pickem_api/tests.py` if the proof endpoint is under `/api/`.

## Proof Wiring Options

Preferred proof wiring is a tiny authenticated route that returns minimal context for a valid family/pool and nothing else. It should not become product UI.

Candidate API proof:

- `GET /api/families/<family_slug>/pools/<pool_slug>/authz-check/`
- requires active family membership;
- returns family slug, pool slug, user role for allowed users;
- returns 401/403/404 according to locked behavior.

Candidate page proof:

- `GET /families/<family_slug>/<pool_slug>/authz-check/`
- browser behavior proves anonymous redirect and 404/403 semantics.

API proof is less user-visible and enough to exercise DRF integration. Page decorator tests can still be written against a small local test view if avoiding a production URL is preferable.

## Migration/Safety Notes

No database migration is required for Phase 2 unless implementation discovers a missing index. The existing Phase 1 indexes on `Family.slug`, `Pool(family, slug, status)`, and `FamilyMembership(family, user, status)` support the planned helper queries.

Do not make tenant foreign keys non-null in Phase 2. Legacy global routes still depend on nullable `pool`/`family` until Phase 4/5 route migration completes.

Do not change the semantics of `is_commissioner` or `commissioner_required` globally in Phase 2. Instead, introduce parallel tenant-aware owner/admin guards so Phase 5 can migrate commissioner functionality deliberately.

## Validation Architecture

Validation should run at three levels:

- unit tests for helper role and object-resolution semantics;
- integration tests for decorators/DRF adapters converting helper denials into correct HTTP behavior;
- regression checks confirming existing global pages/tests still pass after adding the foundation.

The highest-value negative matrix is user A in family A attempting to access family B’s family slug, pool slug, picks/standings proof, and admin proof. Phase 2 should establish the helper-level matrix even before all product pages are migrated.

Commands:

- `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings`
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings`
- `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings`
- `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings`

## Open Questions

- Whether to expose a permanent proof endpoint or use test-only URL wiring. Recommendation: add a minimal API endpoint only if it can be named as internal/diagnostic and does not leak tenant existence.
- Whether later phases should put family/pool slugs under `/families/<family_slug>/pools/<pool_slug>/...` or shorten to `/f/<family_slug>/p/<pool_slug>/...`. Phase 2 helpers should support either route shape.

## RESEARCH COMPLETE
