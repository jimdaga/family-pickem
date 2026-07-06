# Phase 4: Family-Scoped App Pages - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 migrates the user-facing gameplay and community app surface into explicit family/pool context. Dashboard/home, scores, standings, picks, rules, profiles/players, and message board pages should become tenant-aware pages under readable family/pool URLs, with server-side membership checks and tenant-scoped data queries.

This phase should stop signed-in users from using legacy global gameplay pages as private app surfaces. It must not expand into full family admin management, full invite management, owner/admin settings editing, production cron hardening, or new multi-pool UI.

</domain>

<decisions>
## Implementation Decisions

### Tenant URL migration

- **D-01:** Phase 4 should migrate gameplay pages to explicit tenant URLs under `/families/<family_slug>/pools/<pool_slug>/...`.
- **D-02:** Legacy signed-in gameplay routes should redirect to the user's current/default family pool route when the user has a resolvable tenant context.
- **D-03:** Legacy routes should not continue rendering private global gameplay data for signed-in users.
- **D-04:** Anonymous behavior for public/marketing routes may remain public where it already exists, but private gameplay surfaces require authentication and tenant membership.

### Picks and scores behavior

- **D-05:** NFL games, weeks, teams, scores, and schedule reference data remain global.
- **D-06:** Picks, pick counts, "my pick" state, lock/edit state, and any pool/player overlays on score/game pages must be scoped to the current pool.
- **D-07:** Pick submission and edit paths must derive user, family, pool, season/week/game, and correctness-related fields server-side. Client-provided identifiers must be validated against server-resolved tenant context.
- **D-08:** Scores pages may show global NFL game facts, but must not show picks, pick totals, player overlays, or private context from another family/pool.

### Dashboard and standings data boundaries

- **D-09:** Tenant dashboard/home should show only current family/default pool data: current pool standings, weekly winners, pick status, family message preview, and member activity for that family/pool.
- **D-10:** Existing global standings, global league accuracy, global message-board previews, and global pick counts must either be removed from tenant pages or rewritten to be family/pool scoped.
- **D-11:** Standings and weekly winner pages should read from the current pool scope and should deny or redirect legacy global access for signed-in users.
- **D-12:** Cache keys, memoized data, and any derived/precomputed standings used in Phase 4 must include pool/family scope or be avoided until Phase 6 hardening.

### Profiles, players, and message board privacy

- **D-13:** Player lists, member profiles, profile stats, posts, comments, and votes are family-private in Phase 4.
- **D-14:** Active family membership is required before viewing another user's profile or player stats in a family context.
- **D-15:** Profile/stat views should show stats scoped to the requested family/pool context where applicable, not a user's global cross-family picks.
- **D-16:** Message-board posts, comments, votes, create/edit/delete/read endpoints, and AJAX serialization must filter by family/pool scope and deny outsiders.
- **D-17:** Negative tests must prove a member of family A cannot see family B posts, comments, votes, player list, profile stats, or pick data by changing URLs, IDs, query params, or request bodies.

### Rules display

- **D-18:** Phase 4 should make rules pages tenant-aware and display the current family/pool rules/settings in context.
- **D-19:** Rules/settings editing remains Phase 5. Phase 4 should not introduce owner/admin editing forms unless required to remove a data leak.
- **D-20:** A display-only rules page may use existing static rules as fallback copy, but route/context/data access must still be tenant-scoped.

### Route and UX behavior

- **D-21:** Tenant page links in the header, family switcher, dashboard, scores, standings, picks, rules, profiles, and message board should preserve explicit family/pool context.
- **D-22:** Empty states should stay inside the current family/pool context and avoid sending users to global data pages.
- **D-23:** 403/404/not-found behavior should avoid leaking whether another family/pool/profile/post exists where practical.
- **D-24:** Mobile navigation and header context from Phase 3 should remain visible on the migrated pages.

### the agent's Discretion

- Exact plan split and migration order, provided high-risk private data paths are migrated before polish-only work.
- Exact tenant route names, template filenames, partial extraction, and helper names, provided URLs remain readable and explicit.
- Exact dashboard widget composition, provided it only uses current family/pool data.
- Whether to implement small compatibility redirects per route or a shared helper, provided behavior is tested.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning

- `.planning/PROJECT.md` — core value, constraints, and active multi-tenancy requirements.
- `.planning/REQUIREMENTS.md` — Phase 4 requirements `AUTHZ-02`, `AUTHZ-04`, `AUTHZ-05`, `POOL-03`, `POOL-04`, `COMM-02`, `SEC-03`, and `SEC-04`.
- `.planning/ROADMAP.md` — Phase 4 scope and definition of done.
- `.planning/STATE.md` — current project state after Phase 3 completion.

### Prior phase context and summaries

- `.planning/phases/01-domain-schema-foundation/01-CONTEXT.md` — family/pool separation, global NFL reference data, legacy pool/family scope.
- `.planning/phases/01-domain-schema-foundation/01-02-SUMMARY.md` — nullable pool scope and legacy competition data backfill for picks/standings/stats.
- `.planning/phases/01-domain-schema-foundation/01-03-SUMMARY.md` — nullable family scope and backfill for message board, comments, votes, and banners.
- `.planning/phases/02-authorization-foundation/02-CONTEXT.md` — tenant guard behavior, role ladder, explicit context, and denial semantics.
- `.planning/phases/02-authorization-foundation/02-01-SUMMARY.md` — `pickem_api.authz` helper implementation.
- `.planning/phases/02-authorization-foundation/02-02-SUMMARY.md` — browser/API guard adapters and proof endpoint.
- `.planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md` — explicit tenant URL model and switcher/onboarding decisions.
- `.planning/phases/03-onboarding-and-family-selection/03-01-SUMMARY.md` — authenticated root routing, onboarding, picker, tenant pool shell.
- `.planning/phases/03-onboarding-and-family-selection/03-03-SUMMARY.md` — invite/join flow and owner-only invite behavior.
- `.planning/phases/03-onboarding-and-family-selection/03-04-SUMMARY.md` — header/mobile family switcher context.
- `.planning/phases/03-onboarding-and-family-selection/03-05-SUMMARY.md` — final Phase 3 verification and Phase 4 handoff risks.

### Security and discovery docs

- `SECURITY_THREAT_MODEL.md` — tenant isolation risks, BOLA/IDOR mitigations, and negative test expectations.
- `FAMILY_MULTI_TENANCY_PLAN.md` — recommended route, authorization, onboarding, and tenant model.
- `DISCOVERY.md` — current route/API inventory and global leakage risks.
- `TEST_PLAN.md` — unit/integration/E2E authorization negative tests.

### Current code

- `pickem/pickem_api/models.py` — pool-scoped competition models and tenant domain models.
- `pickem/pickem_api/authz.py` — canonical tenant context and membership helpers.
- `pickem/pickem_homepage/authz.py` — browser tenant route guard.
- `pickem/pickem_homepage/models.py` — family-scoped message board and banner models.
- `pickem/pickem_homepage/views.py` — existing global gameplay, profile, message-board, pick, score, standings, rules, and AJAX flows.
- `pickem/pickem_homepage/urls.py` — legacy and Phase 3 tenant route integration points.
- `pickem/pickem_homepage/forms.py` — pick form and onboarding form patterns.
- `pickem/pickem/context_processors.py` — Phase 3 family switcher context and existing global banner/footer context.
- `pickem/pickem_homepage/templates/pickem/base.html` — shared navigation and tenant context visibility.
- `pickem/pickem_homepage/templates/pickem/home.html` — existing dashboard/home global data surface.
- `pickem/pickem_homepage/templates/pickem/picks.html` — existing pick submission surface.
- `pickem/pickem_homepage/templates/pickem/scores.html` — existing scores/game display surface.
- `pickem/pickem_homepage/templates/pickem/standings.html` — existing standings surface.
- `pickem/pickem_homepage/tests.py` — existing route/view/form tests and Phase 3 tenant tests.
- `pickem/pickem_api/tests.py` — tenant domain/authz tests.
- `pickem/pickem/test_settings.py` — isolated test settings.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `pickem_api.authz.require_tenant_context()` and related helpers — canonical way to resolve family/pool and active membership.
- `pickem_homepage.authz.family_member_required` — page decorator for tenant routes, including role requirements where needed.
- Phase 3 route patterns in `pickem_homepage/urls.py` — established slug URL shape under `/families/<family_slug>/pools/<pool_slug>/`.
- Phase 3 templates `family_pool_home.html`, `onboarding.html`, and `family_picker.html` — tenant-shell and empty-state patterns.
- Phase 3 `family_switcher_context` in `pickem/context_processors.py` — header-visible current family/pool context.
- Existing Django `TestCase` route tests — pattern for positive and negative tenant access assertions.

### Established Patterns

- Browser routes are function-based Django views in `pickem_homepage.views`.
- Existing templates are large and mid Bootstrap-to-Tailwind migration; Phase 4 should keep UI edits focused and avoid broad visual rewrites.
- Existing global gameplay views query ORM models directly in views; Phase 4 may add focused helpers if they reduce duplicated tenant filtering and make unsafe access harder.
- Existing NFL games/weeks/teams are global reference data and should stay global for v1.
- Existing pick forms expose too many model fields; Phase 4 pick write migration should reduce client trust and derive server-owned fields.

### Integration Points

- Legacy global routes `/`, `/scores/`, `/standings/`, `/picks/`, `/rules/`, profile/player routes, and message-board AJAX endpoints must either redirect into tenant context or become explicit tenant routes.
- Template links from base/header, dashboard, scores, standings, picks, profiles, rules, and message-board snippets must preserve family/pool slug context.
- Message-board query paths should use the family scope added in Phase 1 and deny outsiders through Phase 2/3 tenant context.
- Picks/standings/stats query paths should use the pool scope added in Phase 1.
- Site-wide public/marketing content can remain public where already intended, but private app widgets must be tenant-scoped.

</code_context>

<specifics>
## Specific Ideas

- The safest route migration model is redirecting signed-in legacy gameplay routes into the user's resolved/default family pool route, rather than maintaining two active private app surfaces.
- Scores should continue showing global NFL game facts, but every pool/player overlay on scores must be current-pool-only.
- The family dashboard should feel like the current family's pool dashboard, not a global league homepage with family labels added.
- Profiles and message board should be treated as family-private by default.
- Rules should be display-only in Phase 4; editing belongs to Phase 5 owner/admin work.

</specifics>

<deferred>
## Deferred Ideas

- Owner/admin editing of rules and family/pool settings remains Phase 5.
- Full invite management, revocation/regeneration UI, role management, member management, and audit-log UI remain Phase 5.
- Cron/scoring production hardening and background pool-aware scoring job changes remain Phase 6 unless Phase 4 research finds a tiny route-adjacent blocker.
- Multi-active-pool UI remains v2/advanced pool scope.

</deferred>

---

*Phase: 04-Family-Scoped App Pages*
*Context gathered: 2026-06-29*
