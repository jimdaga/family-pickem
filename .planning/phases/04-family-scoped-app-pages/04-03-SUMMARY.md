---
phase: 04-family-scoped-app-pages
plan: 03
subsystem: tenant-gameplay-pages
tags: [django, tenant-authz, scores, standings, rules, tests]

requires:
  - phase: 01-domain-schema-foundation
    provides: [Pool scope on picks, standings, and stats; PoolSettings]
  - phase: 02-authorization-foundation
    provides: [tenant context resolution and membership authorization]
  - phase: 03-onboarding-and-family-selection
    provides: [explicit family/pool URLs and tenant header context]
  - phase: 04-family-scoped-app-pages
    provides: [tenant dashboard and pick routes from Plans 01 and 02]
provides:
  - Tenant scores routes for current and selected weeks.
  - Tenant standings route with pool-scoped rows, season champion, and weekly winners.
  - Tenant rules route with display-only current family, pool, and pool settings context.
  - Signed-in legacy scores, standings, and rules redirects before private global rendering.
  - Cross-family negative tests for overlays, standings, rules settings, query params, and outsiders.
affects: [family-private-profiles, shared-navigation-cleanup, phase-04-validation]

tech-stack:
  added: []
  patterns:
    - Tenant browser routes use family_member_required and request.tenant_context.
    - Global NFL facts remain global while pick and standings overlays filter by tenant_context.pool.
    - Display-only tenant settings are rendered from PoolSettings without mutation controls.

key-files:
  created:
    - .planning/phases/04-family-scoped-app-pages/04-03-SUMMARY.md
  modified:
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/templates/pickem/scores.html
    - pickem/pickem_homepage/templates/pickem/standings.html
    - pickem/pickem_homepage/templates/pickem/rules.html
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Signed-in legacy scores, standings, and rules routes redirect to the user's default tenant route before querying private data."
  - "Scores keep GamesAndScores, GameWeeks, and Teams as global NFL reference facts while filtering GamePicks, point overlays, players, weekly stats, and winners by the current pool."
  - "Rules are display-only in Phase 4 and expose current PoolSettings values without owner/admin mutation controls."

patterns-established:
  - "Use render_scores_page(), render_standings_page(), and render_rules_page() helpers with optional tenant_context for legacy anonymous and tenant guarded variants."
  - "Pass pre-scoped weekly_winners context into standings templates instead of using global winner template filters on tenant pages."
  - "Tenant scores and standings avoid global profile links until family-private profile routes are added in Plan 04-04."

requirements-completed: [AUTHZ-04, POOL-03, POOL-04, SEC-03, SEC-04]

coverage:
  - id: D1
    description: "Tenant scores render shared global NFL game facts while exposing only current-pool picks, player overlays, user weekly stats, and week winners."
    requirement: POOL-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.TenantScoresStandingsRulesIsolationTests.test_tenant_scores_current_week_keeps_global_games_but_scopes_private_overlays"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.TenantScoresStandingsRulesIsolationTests.test_tenant_scores_selected_week_uses_global_week_facts_with_pool_only_overlays"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tenant standings, season champion, and weekly winners are current-pool scoped and do not leak another family through query params."
    requirement: POOL-02
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.TenantScoresStandingsRulesIsolationTests.test_tenant_standings_and_weekly_winners_are_current_pool_only"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.TenantScoresStandingsRulesIsolationTests.test_query_params_do_not_switch_standings_pool_or_rules_context"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tenant rules display current family, pool, and PoolSettings values without editing forms."
    requirement: POOL-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.TenantScoresStandingsRulesIsolationTests.test_tenant_rules_display_current_context_settings_and_no_editing_form"
        status: pass
    human_judgment: false
  - id: D4
    description: "Signed-in legacy scores, standings, and rules routes redirect to tenant URLs; outsiders get denied on direct tenant URLs."
    requirement: AUTHZ-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.TenantScoresStandingsRulesIsolationTests.test_legacy_signed_in_scores_standings_and_rules_redirect_before_private_rendering"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.TenantScoresStandingsRulesIsolationTests.test_outsider_direct_tenant_scores_standings_and_rules_are_denied"
        status: pass
    human_judgment: false

duration: 6min 14s
completed: 2026-06-30
status: complete
---

# Phase 04 Plan 03: Tenant Scores, Standings, And Rules Summary

Tenant scores, standings, weekly winners, and rules now run through explicit family/pool context with pool-scoped private overlays.

## Performance

- **Duration:** 6min 14s
- **Started:** 2026-06-30T00:21:36Z
- **Completed:** 2026-06-30T00:27:50Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added tenant routes for scores, selected-week scores, standings, and rules under `/families/<family_slug>/pools/<pool_slug>/`.
- Scoped every scores overlay, pick total, player list, user weekly stat, standings row, season champion, and weekly winner to the current pool while leaving NFL game/team/week facts global.
- Converted signed-in legacy scores, standings, and rules routes into tenant redirects before private global rendering.
- Rendered rules with current family/pool context and display-only `PoolSettings` values.
- Added cross-family negative tests proving outsiders, slug/query tampering, and another family's picks/standings/settings do not leak.

## Task Commits

1. **Task 1: Add scores standings and rules isolation tests** - `916a2e6` (test)
2. **Task 2: Implement tenant scores and standings** - `8b507a6` (feat)
3. **Task 3: Implement tenant rules and update score standings templates** - `50b6cfd` (feat)

**Plan metadata:** recorded in the final `docs(04-03)` commit.

## Files Created/Modified

- `pickem/pickem_homepage/tests.py` - Added tenant scores, standings, rules, redirects, outsider denial, and query-param isolation coverage.
- `pickem/pickem_homepage/urls.py` - Added guarded tenant routes for scores, selected-week scores, standings, and rules.
- `pickem/pickem_homepage/views.py` - Added tenant-aware render helpers and pool-scoped query filters for private overlays and standings data.
- `pickem/pickem_homepage/templates/pickem/scores.html` - Preserves tenant context in private links and empty-state picks links.
- `pickem/pickem_homepage/templates/pickem/standings.html` - Uses scoped `weekly_winners` context and avoids global profile links on tenant renderings.
- `pickem/pickem_homepage/templates/pickem/rules.html` - Displays current family/pool and read-only pool settings values.

## Decisions Made

- Kept anonymous legacy `/scores/`, `/standings/`, and `/rules/` behavior public-compatible for existing smoke tests, while signed-in users redirect before any private global data renders.
- Reused the existing `family_pool_home` URL as a safe tenant-preserving destination for score/standings player links until Plan 04-04 adds family-private profile routes.
- Avoided cache or denormalized global-rank reads for the new tenant standings path; rows and winners come from current-pool querysets.

## Deviations from Plan

### Process Deviations

**1. Test-first task produced an expected red state before implementation**
- **Found during:** Task 1
- **Issue:** The plan was not marked TDD, but Task 1 required tests for tenant route names and scoped behavior that did not exist until Tasks 2 and 3.
- **Fix:** Committed the isolation tests after confirming they failed only for missing tenant routes, then implemented routes, query filters, and templates in separate commits.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** Final `pickem_homepage` suite passed after Tasks 2 and 3.
- **Committed in:** `916a2e6`

**Total deviations:** 1 process deviation  
**Impact on plan:** No behavior scope changed; final verification passed.

## Issues Encountered

- The existing standings template used the global `lookweekwinner` filter, which would leak winners from another pool even after view querysets were scoped. The template now uses the view-provided `weekly_winners` dictionary.
- `views.py` had a duplicate legacy `rules()` definition. The later definition was updated to delegate through the tenant redirect/display helper so it no longer shadows the intended behavior.

## User Setup Required

None - no external service configuration required.

## Known Stubs

- `pickem/pickem_homepage/views.py:1045` has a pre-existing TODO for assigning zero points to users that did not win yet. It was not introduced by this plan and does not block tenant isolation.
- `pickem/pickem_homepage/templates/pickem/scores.html:753-756` has pre-existing JavaScript placeholder markup for a missing "Your Pick" display. It is runtime UI fallback text, not mock data.
- `pickem/pickem_homepage/templates/pickem/standings.html:207` has a pre-existing "TBD" empty weekly-winner placeholder. It remains intentional when no winner exists.

## Threat Flags

None. New browser routes are protected by `family_member_required`; new database reads at the trust boundary filter private picks, standings, and settings through `request.tenant_context.pool` or `request.tenant_context.family`.

## Verification

- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` - 89 tests passed.
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - system check identified no issues.
- PASS: `curl -s --max-time 5 http://localhost:8000/scores/ | head -40` - returned anonymous scores HTML.

## Next Phase Readiness

Plan 04-04 can add family-private profiles, players, and message-board AJAX. Score and standings player links currently stay inside the tenant pool context instead of linking to global profiles, leaving the final tenant profile destination for Plan 04-04.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/04-family-scoped-app-pages/04-03-SUMMARY.md`.
- Modified files exist: `pickem/pickem_homepage/views.py`, `pickem/pickem_homepage/urls.py`, `pickem/pickem_homepage/templates/pickem/scores.html`, `pickem/pickem_homepage/templates/pickem/standings.html`, `pickem/pickem_homepage/templates/pickem/rules.html`, and `pickem/pickem_homepage/tests.py`.
- Task commits exist: `916a2e6`, `8b507a6`, and `50b6cfd`.
- No tracked files were deleted by task commits.

---
*Phase: 04-family-scoped-app-pages*
*Completed: 2026-06-30*
