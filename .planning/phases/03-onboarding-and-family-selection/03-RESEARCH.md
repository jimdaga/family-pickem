# Phase 03 Research: Onboarding And Family Selection

## Executive Summary

Phase 3 should add a narrow authenticated routing and onboarding layer in `pickem_homepage`, not migrate gameplay pages yet. The root path can stay public for anonymous users, but signed-in users should be routed by active family membership count before they see global homepage standings, picks, message-board data, or league stats. [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md] [VERIFIED: pickem/pickem_homepage/views.py]

Use the tenant schema and authz foundation already delivered in Phases 1 and 2: `Family`, `Pool`, `FamilyMembership`, `FamilyInvitation`, `PoolSettings`, `FamilyAuditLog`, `get_user_family_memberships()`, and `family_member_required()`. No external packages are needed. [VERIFIED: pickem/pickem_api/models.py] [VERIFIED: pickem/pickem_api/authz.py] [VERIFIED: pickem/pickem_homepage/authz.py]

Primary recommendation: implement a small set of Phase 3 routes for `/onboarding/`, `/families/create/`, `/families/join/`, invite acceptance, family picker, and `/families/<family_slug>/pools/<pool_slug>/`, with all mutations POST-only, CSRF-protected, and backed by active-membership checks. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: SECURITY_THREAT_MODEL.md]

## Current Code Findings

- `LOGIN_REDIRECT_URL = '/'`, so post-login behavior currently returns users to the global `index` view. [VERIFIED: pickem/pickem/settings.py]
- `index()` renders global standings, global message-board posts, global pick counts, global league accuracy, and current-week pick status for signed-in users. A no-family signed-in user would therefore see global league data unless Phase 3 redirects before rendering this view. [VERIFIED: pickem/pickem_homepage/views.py]
- Existing browser routes are global (`/`, `/scores/`, `/standings/`, `/rules/`, `/picks/`, `/profile/`, message-board and commissioner routes). There are no `/families/<family_slug>/pools/<pool_slug>/...` browser routes yet. [VERIFIED: pickem/pickem_homepage/urls.py]
- `Family`, `Pool`, `FamilyMembership`, `FamilyInvitation`, `PoolSettings`, and `FamilyAuditLog` already exist. `FamilyInvitation` stores `code_hash`, lifecycle fields, optional pool, role, expiry, revocation, max uses, and use count; it has no raw code field. [VERIFIED: pickem/pickem_api/models.py] [VERIFIED: .planning/phases/01-domain-schema-foundation/01-01-SUMMARY.md]
- Phase 2 helpers require explicit active membership; superusers and legacy commissioners do not bypass tenant checks. Non-members are treated as not found; in-family wrong-role access is permission denied. [VERIFIED: pickem/pickem_api/authz.py] [VERIFIED: .planning/phases/02-authorization-foundation/02-01-SUMMARY.md]
- `family_member_required()` already attaches `request.tenant_context` for authorized browser routes and maps anonymous users to login redirects, non-members to 404, and wrong-role users to 403. [VERIFIED: pickem/pickem_homepage/authz.py] [VERIFIED: pickem/pickem_homepage/tests.py]
- The shared `base.html` header is the correct insertion point for current family/pool context and switcher UI. It already has desktop/mobile nav branches and uses context processors for user state and commissioner nav. [VERIFIED: pickem/pickem_homepage/templates/pickem/base.html] [VERIFIED: pickem/pickem/context_processors.py]
- Current JSON mutations include some `@csrf_exempt` endpoints (`check_username`, `toggle_theme`, and some commissioner actions). Phase 3 should not copy that exemption pattern for create-family, invite creation, or invite acceptance. [VERIFIED: pickem/pickem_homepage/views.py] [CITED: SECURITY_THREAT_MODEL.md]

## Recommended Implementation Shape

- Add a small post-login routing helper, preferably called from `index()` for authenticated requests or from a dedicated redirect view targeted by `LOGIN_REDIRECT_URL`. The helper should call `get_user_family_memberships(request.user)` and branch: zero active memberships to onboarding, one active membership to that family's default active pool, multiple active memberships to a family picker unless a valid explicit destination is already being requested. [VERIFIED: pickem/pickem_api/authz.py] [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md]
- Resolve the default pool with `Pool.objects.filter(family=family, status=Pool.Status.ACTIVE, is_default=True).order_by('-season', 'slug').first()`, falling back to the first active pool only if no default exists. If no active pool exists for an active family, show a safe owner/admin repair path or generic unavailable state; do not fall back to global pages. [VERIFIED: pickem/pickem_api/models.py] [ASSUMED: implementation detail]
- Create-family should be one transaction: validate a family-name-only form, generate a deterministic unique `Family.slug`, create `Family`, create current-season default NFL `Pool`, create `PoolSettings`, create active owner `FamilyMembership`, add `FamilyAuditLog` rows for membership creation and/or onboarding-sensitive actions, then redirect to `/families/<family_slug>/pools/<pool_slug>/`. [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md] [VERIFIED: pickem/pickem_api/models.py]
- Pool creation should use `pickem.utils.get_season()` for the season, `competition='nfl'`, `is_default=True`, and a simple default pool name such as `<season display> Pickem` or `Main Pickem`. This follows Phase 1 current-season/default-pool conventions without adding multi-pool UI. [VERIFIED: AGENTS.md] [VERIFIED: .planning/phases/01-domain-schema-foundation/01-02-SUMMARY.md] [ASSUMED: exact copy]
- Invite creation for Phase 3 should be owner-only and minimal: generate a high-entropy raw code, hash it before saving, persist only `FamilyInvitation.code_hash`, set role to `member`, optionally attach the default pool, set conservative expiry/max-use defaults if chosen, return/show the raw code/link once, and audit `INVITATION_CREATED`. [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md] [VERIFIED: pickem/pickem_api/models.py] [CITED: SECURITY_THREAT_MODEL.md]
- Invite acceptance should accept both a link code and manually entered code, normalize only for transport/readability, hash server-side, find a non-revoked unexpired invitation with remaining uses, verify invitation family/pool are active and consistent, then create or reactivate the user's `FamilyMembership` with the invitation role. [VERIFIED: pickem/pickem_api/models.py] [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md]
- Use a database transaction plus row locking where feasible around invitation acceptance to avoid `use_count` races. At minimum, increment `use_count` in the same transaction as membership create/reactivate and re-check `max_uses` immediately before saving. [ASSUMED: implementation detail based on Django ORM patterns]
- Header switcher data should come from a context processor or a lightweight helper used by tenant entry views. It must list only `get_user_family_memberships()` results, select each family's default active pool, and hide inactive memberships/families/pools. [VERIFIED: pickem/pickem_api/authz.py] [VERIFIED: pickem/pickem_homepage/templates/pickem/base.html] [VERIFIED: pickem/pickem/context_processors.py]
- The first tenant entry route can be a lightweight "pool home/bridge" page at `/families/<family_slug>/pools/<pool_slug>/` protected by `@family_member_required`. It should show context, actions, and compatibility links, but should not attempt to tenant-scope existing picks/scores/standings/message-board pages in Phase 3. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: .planning/phases/02-authorization-foundation/02-03-SUMMARY.md]

## Security Findings

- IDOR/BOLA is the main risk for Phase 3. Every new route containing `family_slug`, `pool_slug`, invitation id/code, or membership state must resolve server-side and avoid trusting client-provided family, pool, user, season, or role fields. [CITED: SECURITY_THREAT_MODEL.md] [VERIFIED: pickem/pickem_api/authz.py]
- No-family signed-in users must be blocked from global private data by redirecting before `index()` computes global standings, message-board posts, pick counts, and user pick status. [VERIFIED: pickem/pickem_homepage/views.py] [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md]
- Invite brute force requires high-entropy codes, hashed storage, generic failure messages, expiry/revocation/max-use checks, and test coverage. Rate limiting is configured but disabled in development and `django_ratelimit` is not active, so Phase 3 should not rely on installed rate limiting for correctness. [VERIFIED: pickem/pickem/settings.py] [CITED: SECURITY_THREAT_MODEL.md]
- Raw invite codes must never be stored, logged, displayed in admin, or included in audit metadata. Store only the hash and show the raw code/link only in the creation response/page. [VERIFIED: pickem/pickem_api/models.py] [VERIFIED: .planning/phases/01-domain-schema-foundation/01-01-SUMMARY.md]
- Inactive memberships, inactive families, inactive/archived pools, revoked invitations, expired invitations, exhausted invitations, and pool-family mismatches must all fail closed. [VERIFIED: pickem/pickem_api/authz.py] [VERIFIED: pickem/pickem_api/models.py]
- CSRF protection must stay enabled for session-authenticated create-family, create-invite, and accept-invite endpoints. Do not add `@csrf_exempt`; use standard Django forms for HTML and include CSRF headers/tokens for any JSON endpoint. [VERIFIED: pickem/pickem_homepage/views.py] [CITED: SECURITY_THREAT_MODEL.md]
- Owner-only minimal invite creation is the safest Phase 3 default because full admin invite policy is deferred to Phase 5 and current legacy commissioner status is global, not tenant authority. [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md] [VERIFIED: .planning/STATE.md]

## UX Findings

- The no-family screen should be focused and non-dashboard-like: short copy, one primary create-family form, one join-by-code form/link path, plus sign-out/back navigation. This prevents a signed-in no-family user from landing on global league data. [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md]
- The create-family flow should ask only for family name in Phase 3. Pool naming should stay implicit unless the implementation finds a trivial low-cost pattern; this keeps onboarding short and matches the locked decision. [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md]
- Multi-family users need a dedicated picker or obvious header switcher path before entering gameplay context. The switcher should show family name and default pool name, not just an icon. [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md] [ASSUMED: UX recommendation]
- Keep the UI consistent with the existing Tailwind-moving `base.html` and `home.html` patterns. Do not start a broad redesign or migrate Bootstrap remnants as part of Phase 3. [VERIFIED: AGENTS.md] [VERIFIED: pickem/pickem_homepage/templates/pickem/base.html]
- New readable tenant URLs should be explicit and bookmarkable: `/families/<family_slug>/pools/<pool_slug>/`, plus create/join/picker routes. Existing global gameplay links can remain compatibility bridges until Phase 4. [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md] [VERIFIED: FAMILY_MULTI_TENANCY_PLAN.md]

## Test Strategy

- Add homepage/view tests for post-login routing: anonymous `/` still returns the public homepage; authenticated zero-family user redirects to onboarding; one-family user redirects to default pool entry; multi-family user redirects to picker or sees a picker. [VERIFIED: pickem/pickem_homepage/tests.py] [VERIFIED: TEST_PLAN.md]
- Add create-family tests: login required, GET renders form, POST creates family/default pool/settings/owner membership/audit entry, slug collisions are handled, and redirect target is the new tenant URL. [VERIFIED: pickem/pickem_api/models.py] [VERIFIED: .planning/REQUIREMENTS.md]
- Add invite creation tests: non-owner/member denied, owner allowed, raw code is returned once, stored row has only `code_hash`, audit row is created, and generated link targets the accept route. [VERIFIED: pickem/pickem_api/models.py] [CITED: SECURITY_THREAT_MODEL.md]
- Add invite acceptance tests: anonymous redirects to login; valid code creates active membership and increments use count; inactive existing membership is reactivated; revoked, expired, exhausted, wrong-hash, inactive-family, inactive-pool, and pool-family mismatch cases fail with safe errors and no membership. [VERIFIED: pickem/pickem_api/models.py] [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md]
- Add header/switcher template tests: active family/pool context appears on tenant entry pages; only active memberships are listed; inactive membership/family/pool and outsider families do not render. [VERIFIED: pickem/pickem_api/authz.py] [VERIFIED: pickem/pickem_homepage/templates/pickem/base.html]
- Add CSRF tests with `Client(enforce_csrf_checks=True)` for POST create-family, create-invite, and accept-invite if implemented as forms/JSON mutations. Missing token should return 403. [VERIFIED: django test pattern in pickem/pickem_homepage/tests.py] [CITED: SECURITY_THREAT_MODEL.md]
- Run focused and full validation commands after implementation: `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings`, `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings`, and `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings`. [VERIFIED: .planning/STATE.md] [VERIFIED: pickem/pickem/test_settings.py]

## Scope Boundaries

- Do not tenant-scope dashboard/home, scores, standings, picks, rules, profiles, or message board data in Phase 3 beyond the lightweight tenant entry point and no-family redirect guard. That belongs to Phase 4. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md]
- Do not build full invite management: no revoke/regenerate/list UI, no advanced expiry editor, no audit-log display, and no broad admin invite dashboard. That belongs to Phase 5. [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md]
- Do not migrate global commissioner behavior to family admin in Phase 3, except for the minimal owner-only invite creation control needed for onboarding. Full family admin is Phase 5. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: .planning/STATE.md]
- Do not add multi-pool selection UI. Route/switcher can target each family's default active pool. [VERIFIED: .planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md]
- Do not add new packages, new auth providers, or database-hardening constraints in Phase 3. Existing Django/allauth/domain models are sufficient for the requested flow. [VERIFIED: pickem/pickem/settings.py] [VERIFIED: pickem/pickem_api/models.py]

## Validation Architecture

| Requirement | Behavior | Test Type | Command |
|---|---|---|---|
| TEN-01 | Signed-in user creates family, default current-season pool, pool settings, owner membership, and audit trail | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` |
| INV-01 | Owner can create a minimal invite link/code without raw code storage | integration/unit | `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings` |
| INV-03 | Signed-in no-family user sees onboarding and not global league data | integration/template | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` |
| INV-04 | Multi-family user can choose/switch active family default pool | integration/template | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` |
| AUTHZ-03 | Invite creation requires owner role in Phase 3 | negative integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` |
| SEC-02 | Session-authenticated create/join/invite mutations reject missing CSRF token | security integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` |
| SEC-03 | Cross-family picker/invite/tenant-entry access is denied or hidden | negative integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings` |

Recommended phase gate:

```bash
cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings
cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings
cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2
```

Validation is enabled because `.planning/config.json` does not set `workflow.nyquist_validation` to `false`. [VERIFIED: .planning/config.json]

## Open Questions (RESOLVED)

1. RESOLVED: Invite acceptance should reactivate an inactive membership automatically only when the invitation is valid, active, unexpired, unexhausted, belongs to the same active family/pool, and the user is accepting for that same family. The update must be audited. [ASSUMED: product/security policy]

2. RESOLVED: Minimal Phase 3 owner-created invites should default to `expires_at = timezone.now() + timedelta(days=14)` and `max_uses = 20`. Do not expose advanced expiry/use-count editing until Phase 5. [ASSUMED: product policy]

3. RESOLVED: Keep root `/` public for anonymous visitors and perform authenticated membership-count routing at the start of `index()` before global data is queried. This avoids changing allauth settings in Phase 3 while meeting the no-family isolation requirement. [VERIFIED: pickem/pickem/settings.py] [VERIFIED: pickem/pickem_homepage/views.py]

## RESEARCH COMPLETE

Research complete for Phase 03. Planner can proceed with a bounded implementation plan for onboarding, create-family/default-pool creation, minimal invite generation/acceptance, header switcher, and negative tests without migrating broad gameplay pages.
