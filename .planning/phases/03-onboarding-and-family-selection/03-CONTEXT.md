# Phase 3: Onboarding And Family Selection - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers the signed-in user's path into an authorized family/pool context: post-login routing, no-family onboarding, create-family, join-by-invite, and a visible family/pool switcher. It should make the current family/pool context clear and reachable without migrating the full gameplay surface yet.

This phase must not broaden into Phase 4's full tenant-scoped dashboard/picks/standings/message-board migration or Phase 5's full family admin experience.

</domain>

<decisions>
## Implementation Decisions

### Post-login routing

- **D-01:** After Google sign-in, route users by active family membership count.
- **D-02:** A signed-in user with zero active families should see a focused onboarding screen with create-family and join-family actions.
- **D-03:** A signed-in user with exactly one active family should land directly in that family's default pool context.
- **D-04:** A signed-in user with multiple active families should see a clear family picker or switcher path before entering a pool context.

### Create-family flow

- **D-05:** Creating a family in Phase 3 should create the family plus one default current-season NFL pool in one flow.
- **D-06:** The create-family form should ask for the family name only unless the planner finds an existing low-cost pattern for optional pool naming.
- **D-07:** The creator becomes the family owner.
- **D-08:** The new pool should be the family's default pool and use the existing season/current-season conventions from Phase 1.

### Join-family flow

- **D-09:** Users should be able to join with an invite code or invite link.
- **D-10:** Invite acceptance should create or activate the user's family membership using the invitation's role, normally `member`.
- **D-11:** After a successful join, the user should land in the joined family's default pool context.
- **D-12:** Join attempts must validate invitation state server-side: code hash, family, optional pool, expiry, revocation, and max-use/use-count behavior where feasible.

### Invite minimum for Phase 3

- **D-13:** Phase 3 should include a minimal owner-created member invite link/code so a newly created family can invite others.
- **D-14:** Full invite management stays in Phase 5. Revocation/regeneration/list management, advanced expiry editing, and invite audit UI should not be pulled into Phase 3 unless needed for a secure minimal invite.
- **D-15:** Raw invite codes must be shown only at creation/response time and never stored at rest. Persist only the existing `FamilyInvitation.code_hash`.

### Family switcher and current context

- **D-16:** Show the current family/pool context in the header/navigation for signed-in users once they are in tenant context.
- **D-17:** Multi-family users should be able to switch family/pool from the header.
- **D-18:** The switcher should use active memberships only and must not expose families where the user lacks active membership.
- **D-19:** The switcher can initially target each family's default pool; multi-pool selection is schema-supported but not a required Phase 3 UI.

### Empty states

- **D-20:** Users with no family should see a focused onboarding screen, not global standings, global picks, or global league data.
- **D-21:** Onboarding copy should be concise and friendly, with primary actions for creating a family and joining with an invite.
- **D-22:** Avoid dead-end screens: every no-family path should offer create, join, and sign-out/back options where appropriate.

### URL shape

- **D-23:** New tenant-aware URLs should use readable slugs: `/families/<family_slug>/pools/<pool_slug>/...`.
- **D-24:** New Phase 3 routes should preserve explicit family/pool context rather than relying only on session state.
- **D-25:** Existing global gameplay routes may remain as compatibility bridges until Phase 4 migrates them.

### Authorization boundaries

- **D-26:** Use Phase 2 tenant authorization helpers for all family/pool reads and writes introduced in Phase 3.
- **D-27:** Creating a family requires authentication but no existing membership.
- **D-28:** Creating invites requires at least owner permission in Phase 3's minimal invite flow, unless the planner identifies a strong reason to allow admins for this specific action.
- **D-29:** Joining by invite requires authentication, but the user does not need existing family membership.

### the agent's Discretion

- Exact page names, template filenames, form class names, helper names, and copy wording.
- Exact slug-generation behavior, provided collisions are handled deterministically and safely.
- Whether post-login routing is implemented via `LOGIN_REDIRECT_URL`, a landing view, middleware-like helper, or explicit view redirects, provided behavior is tested.
- Whether the family picker is a dedicated page or a route reached by the header switcher, provided multiple-family users have a clear path.
- Whether minimal invite creation appears on the onboarding success/family context page or a small owner-only control, provided it does not become full Phase 5 invite management.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning

- `.planning/PROJECT.md` — project value, active requirements, and constraints.
- `.planning/REQUIREMENTS.md` — Phase 3 requirements `TEN-01`, `INV-01`, `INV-03`, `INV-04`, and related authorization requirements.
- `.planning/ROADMAP.md` — Phase 3 scope and definition of done.
- `.planning/STATE.md` — current project state after Phase 2.

### Prior phase decisions

- `.planning/phases/01-domain-schema-foundation/01-CONTEXT.md` — family/pool separation, default pool, invitation hashing, and legacy compatibility decisions.
- `.planning/phases/01-domain-schema-foundation/01-01-SUMMARY.md` — core family/pool/membership/invitation/audit models.
- `.planning/phases/01-domain-schema-foundation/01-02-SUMMARY.md` — default legacy pool conventions and membership backfill.
- `.planning/phases/02-authorization-foundation/02-CONTEXT.md` — tenant guard behavior, role ladder, and explicit context requirements.
- `.planning/phases/02-authorization-foundation/02-01-SUMMARY.md` — `pickem_api.authz` helper implementation.
- `.planning/phases/02-authorization-foundation/02-02-SUMMARY.md` — browser/API guard adapters and proof endpoint.
- `.planning/phases/02-authorization-foundation/02-03-SUMMARY.md` — Phase 2 verification and remaining route migration risks.

### Security and UX docs

- `SECURITY_THREAT_MODEL.md` — tenant isolation risks and required mitigations.
- `FAMILY_MULTI_TENANCY_PLAN.md` — recommended onboarding, URL, and authorization model.
- `DISCOVERY.md` — current route/auth/UI inventory.
- `TEST_PLAN.md` — onboarding and authorization negative test expectations.

### Current code

- `pickem/pickem/settings.py` — Google/allauth login redirect settings.
- `pickem/pickem/urls.py` — root URL inclusion for homepage and API apps.
- `pickem/pickem_api/models.py` — `Family`, `Pool`, `FamilyMembership`, `FamilyInvitation`, `PoolSettings`, and audit models.
- `pickem/pickem_api/authz.py` — Phase 2 tenant authorization helpers.
- `pickem/pickem_homepage/authz.py` — Phase 2 browser guard adapter.
- `pickem/pickem_homepage/views.py` — existing page views, profile flow, message board, and commissioner patterns.
- `pickem/pickem_homepage/urls.py` — current global browser routes.
- `pickem/pickem_homepage/templates/pickem/base.html` — shared layout/header/navigation integration point.
- `pickem/pickem_homepage/templates/pickem/home.html` — current landing/home pattern.
- `pickem/pickem_homepage/forms.py` — existing Django form patterns.
- `pickem/pickem_api/tests.py` — model/authz test patterns.
- `pickem/pickem_homepage/tests.py` — route/view/form test patterns.
- `pickem/pickem/test_settings.py` — test settings.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `pickem_api.models.Family`, `Pool`, `FamilyMembership`, `FamilyInvitation`, `PoolSettings` — Phase 3 domain objects already exist.
- `pickem_api.authz` — canonical membership/role/pool context checks for new tenant routes.
- `pickem_homepage.authz.family_member_required` — browser decorator for tenant context routes.
- `pickem_homepage.views.profile`, `check_username`, and `toggle_theme` — examples of authenticated page/form/JSON handling.
- `pickem_homepage.templates.pickem.base.html` — header/nav insertion point for family switcher.

### Established Patterns

- Browser routes and templates live in `pickem_homepage`.
- Existing tests use Django `TestCase`, `Client`, `RequestFactory`, and inline ORM fixtures.
- Existing auth uses django-allauth/Google sign-in with `LOGIN_REDIRECT_URL = '/'`.
- Existing UI is mid Bootstrap-to-Tailwind migration; keep new onboarding/switcher UI consistent with current templates and Tailwind direction without a broad redesign.

### Integration Points

- Post-login routing must connect to existing root/home behavior without breaking public landing access for anonymous users.
- New create/join/switch routes should be added in `pickem_homepage/urls.py`.
- Invite creation/acceptance must use `FamilyInvitation.code_hash`; raw invite codes are transient.
- New tenant context URLs should follow `/families/<family_slug>/pools/<pool_slug>/...`.
- Phase 3 should create entry points into tenant context but leave full dashboard/picks/standings scoping to Phase 4.

</code_context>

<specifics>
## Specific Ideas

- The no-family user should not see global league data after sign-in.
- The family switcher should make the active family/pool visible enough that users do not wonder which pool they are using.
- New family creation should feel short: name the family, then arrive in the family/default-pool context.
- Joining by invite should support both clicked links and manually entered codes.

</specifics>

<deferred>
## Deferred Ideas

- Full invite management, including revoke, regenerate, invite listing, advanced expiry/max-use UI, and audit-log display, remains Phase 5.
- Full tenant-scoped dashboard, scores, standings, picks, rules, profiles, and message board remain Phase 4.
- Multi-active-pool UI remains v2/advanced pool scope unless a later phase chooses to expose it.

</deferred>

---

*Phase: 3-Onboarding And Family Selection*
*Context gathered: 2026-06-29*
