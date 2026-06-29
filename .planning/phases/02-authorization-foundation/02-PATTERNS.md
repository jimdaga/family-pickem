# Phase 02 Patterns: Authorization Foundation

## Closest Existing Patterns

`pickem_homepage.views.commissioner_required` is the closest existing decorator pattern. It wraps function-based views and handles anonymous and unauthorized browser users. Phase 2 should mirror the wrapper style but replace global commissioner checks with membership/role checks.

`pickem_api.permissions.IsAdminOrReadOnly` is the existing DRF permission extension point. Keep it for global data endpoints, and add tenant-aware helpers/permissions alongside it rather than mixing staff and family authorization.

Phase 1 model tests in `pickem_api/tests.py` are the closest fixture pattern for creating `Family`, `Pool`, `FamilyMembership`, `PoolSettings`, and multiple users. Reuse that simple `TestCase` style first.

Phase 1 homepage tests in `pickem_homepage/tests.py` are the closest pattern for homepage family scope and admin registration checks.

## Recommended New Files

- `pickem/pickem_api/authz.py` — canonical family/pool resolution, role hierarchy, and denial exceptions.
- `pickem/pickem_api/tests/test_authz.py` or new test classes in `pickem/pickem_api/tests.py` — helper-level tests.
- `pickem/pickem_homepage/authz.py` — browser/page decorators that adapt `pickem_api.authz` exceptions to redirect/404/403.
- `pickem/pickem_homepage/tests/test_authz_views.py` or new test classes in `pickem_homepage/tests.py` — decorator/proof page tests.

If the project prefers not to split tests yet, appending focused classes to existing `tests.py` files matches current layout.

## Recommended Existing Files to Touch

- `pickem/pickem_api/permissions.py` — add DRF adapter or permission helper for family-scoped endpoints.
- `pickem/pickem_api/views.py` — optionally add one small proof endpoint.
- `pickem/pickem_api/urls.py` — optionally route the proof endpoint.
- `pickem/pickem_homepage/views.py` — avoid broad edits; only import/use browser authz wrappers if adding a proof page.
- `pickem/pickem_homepage/urls.py` — only if adding a page proof route.
- `.planning/ROADMAP.md` and `.planning/STATE.md` — update planning status.

## Test Patterns

Use `django.test.TestCase` and `Client`/`self.client` as existing tests do.

Core fixture shape:

- create `family_a`, `family_b`;
- create `pool_a` under `family_a`, `pool_b` under `family_b`;
- create users: owner, admin, member, inactive_member, outsider, superuser, commissioner;
- create `FamilyMembership` rows only where intentional;
- create `UserProfile(is_commissioner=True)` for the commissioner-bypass regression.

Assertions should check semantic exceptions at unit level and HTTP codes at adapter/proof level.

## Patterns to Avoid

- Do not call `is_commissioner()` inside family/pool helpers.
- Do not trust a submitted `family_id`, `pool_id`, `family_slug`, or `pool_slug` without resolving membership server-side.
- Do not filter by pool alone when a family is also supplied; validate `pool.family_id == family.id`.
- Do not return detailed API errors such as “family exists but you are not a member” for non-members.
- Do not retrofit all existing routes in this phase; that belongs to Phase 4/5.
- Do not make nullable tenant FKs non-null while legacy global routes remain.

## Plan Inputs

Plan 02-01 should build and test `pickem_api.authz`.

Plan 02-02 should add browser/DRF adapters and a tiny proof integration if still useful after helper tests.

Plan 02-03 should run full verification, update docs/state, and record remaining route migration risks for Phase 3/4/5.

## PATTERNS COMPLETE
