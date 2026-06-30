---
phase: 04-family-scoped-app-pages
plan: 05
subsystem: tenant-navigation-context
tags: [django, templates, context-processors, tenant-isolation, tests]

requires:
  - phase: 04-family-scoped-app-pages
    provides: [tenant dashboard, picks, scores, standings, rules, profiles, message-board routes]
provides:
  - Tenant-preserving shared header and mobile navigation links.
  - Tenant-preserving dashboard, picks, and scores template links.
  - Pool-scoped shared footer private stats.
  - Family-safe shared banner selection.
affects: [phase-04-family-scoped-app-pages, phase-05-family-admin-experience, phase-06-production-migration-and-hardening]

tech-stack:
  added: []
  patterns: [Django named tenant URLs in shared templates, tenant-aware context processor lookup, red-green regression coverage]

key-files:
  created:
    - .planning/phases/04-family-scoped-app-pages/04-05-SUMMARY.md
  modified:
    - pickem/pickem_homepage/tests.py
    - pickem/pickem/context_processors.py
    - pickem/pickem_homepage/templates/pickem/base.html
    - pickem/pickem_homepage/templates/pickem/home.html
    - pickem/pickem_homepage/templates/pickem/picks.html
    - pickem/pickem_homepage/templates/pickem/scores.html

key-decisions:
  - "Shared context processors resolve tenant context from request.tenant_context or authorized route slugs before exposing private stats or family banners."
  - "Footer private stats are suppressed when no safe current pool can be resolved."
  - "Tenant pages prefer current-family banners and fall back only to site-wide banners, never another family's banner."
  - "Template links use named tenant routes where current family/pool context exists, with public-safe legacy fallbacks for anonymous pages."

patterns-established:
  - "Use current_family/current_pool in shared templates to choose tenant route names."
  - "Use request tenant context as an isolation boundary for shared context processors."
  - "When pre-existing dirty template style edits overlap plan hunks, document file-level staging explicitly."

requirements-completed: [AUTHZ-04, SEC-03, SEC-04]

coverage:
  - id: D1
    description: "Shared header and mobile navigation preserve current family/pool URLs for signed-in tenant pages."
    requirement: AUTHZ-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.Phase4SharedContextScopeTests.test_shared_header_links_preserve_current_family_pool_context"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tenant picks and scores template links/forms stay inside the current family/pool context."
    requirement: AUTHZ-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.Phase4SharedContextScopeTests.test_tenant_pick_empty_links_and_ajax_urls_preserve_context"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.Phase4SharedContextScopeTests.test_tenant_scores_private_links_preserve_context"
        status: pass
    human_judgment: false
  - id: D3
    description: "Shared footer stats are current-pool scoped or suppressed when no safe tenant pool exists."
    requirement: SEC-04
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.Phase4SharedContextScopeTests.test_footer_stats_context_scopes_private_stats_to_current_pool"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.Phase4SharedContextScopeTests.test_footer_stats_context_suppresses_private_stats_without_safe_pool"
        status: pass
    human_judgment: false
  - id: D4
    description: "Tenant pages do not render another family's banner."
    requirement: SEC-03
    verification:
      - kind: integration
        ref: "pickem_homepage.tests.Phase4SharedContextScopeTests.test_site_banner_context_does_not_show_another_family_banner_on_tenant_page"
        status: pass
      - kind: integration
        ref: "pickem_homepage.tests.Phase4SharedContextScopeTests.test_site_banner_context_allows_site_wide_banner_when_current_family_has_none"
        status: pass
    human_judgment: false

duration: 42min
completed: 2026-06-30
status: complete
---

# Phase 04 Plan 05: Shared Tenant Navigation And Context Summary

Shared navigation, footer stats, banners, dashboard links, picks links, and scores links now preserve explicit family/pool context on tenant pages.

## Performance

- **Duration:** 42min
- **Started:** 2026-06-30T19:19:00Z
- **Completed:** 2026-06-30T20:01:15Z
- **Tasks:** 3
- **Files modified:** 6 runtime/test files plus this summary

## Accomplishments

- Added `Phase4SharedContextScopeTests` covering tenant-aware shared header/mobile links, tenant picks/scores links, footer stats scoping/suppression, and family-safe banner selection.
- Updated shared context processors so `footer_stats_context` only reads pool-scoped private stats and `site_banner_context` only selects current-family or site-wide banners on tenant pages.
- Updated shared header/mobile navigation, profile menu links, bottom submit-picks link, dashboard actions, picks empty-state buttons, and scores profile links to use tenant route names when family/pool context exists.

## Task Commits

1. **Task 1: Add shared link and context leakage regression tests** - `5c0a541` (test)
2. **Task 2: Clean up shared header links and context processors** - `ba59c16` (feat)
3. **Task 3: Clean up dashboard picks and scores tenant links** - `c8ad686` (feat)

**Plan metadata:** recorded in the final `docs(04-05)` commit.

## Files Created/Modified

- `pickem/pickem_homepage/tests.py` - Added regression coverage for tenant-preserving links and shared context leakage boundaries.
- `pickem/pickem/context_processors.py` - Added shared tenant-context resolution, family-safe banner lookup, and pool-scoped/suppressed footer private stats.
- `pickem/pickem_homepage/templates/pickem/base.html` - Routed shared desktop/mobile/header/profile/bottom-bar links through tenant URLs when current context exists.
- `pickem/pickem_homepage/templates/pickem/home.html` - Routed dashboard score, standings, rules, picks, and profile links through tenant URLs when context exists.
- `pickem/pickem_homepage/templates/pickem/picks.html` - Routed tenant empty-state buttons to tenant scores and standings.
- `pickem/pickem_homepage/templates/pickem/scores.html` - Routed private score overlay and winner profile links to tenant profile URLs.

## Decisions Made

- Reused authorized tenant resolution in shared context processors rather than trusting path strings alone.
- Suppressed footer rank/current-week private stats on authenticated non-tenant pages when no safe current pool can be resolved.
- Preserved anonymous/public fallbacks for public routes while switching signed-in tenant pages to explicit family/pool route names.

## Deviations from Plan

### Process Deviations

**1. Test-first task produced expected red coverage before implementation**
- **Found during:** Task 1
- **Issue:** Task 1 required regression tests for behavior fixed by Tasks 2 and 3, so the focused class failed before implementation.
- **Fix:** Committed the test-only regression coverage, then implemented context/template changes and reran the focused and full suites to green.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** `Phase4SharedContextScopeTests` passed after Tasks 2 and 3.
- **Committed in:** `5c0a541`

**2. Dirty template hunks required file-level staging for plan target files**
- **Found during:** Tasks 2 and 3
- **Issue:** The user intentionally had uncommitted frontend/style refactor edits in `base.html`, `home.html`, `picks.html`, and `scores.html`. The saved pre-wave dirty snapshot could not be cleanly reversed from the index because several style hunks overlapped the tenant-link edits.
- **Fix:** Staged the affected plan-target template files at file level after confirming the plan behavior passed. Unrelated dirty files and `THEME_CONTRACT.md` were left uncommitted.
- **Files modified:** `pickem/pickem_homepage/templates/pickem/base.html`, `home.html`, `picks.html`, `scores.html`
- **Verification:** Full plan verification passed after commits.
- **Committed in:** `ba59c16`, `c8ad686`

**3. GSD state handlers required corrective metadata patch**
- **Found during:** Metadata close-out
- **Issue:** `state.update-progress` reported 94% progress but left `percent: 38` in STATE frontmatter, and `state patch` reported success without updating `stopped_at`.
- **Fix:** Applied a minimal STATE metadata correction after the registered handlers ran, keeping the handler-produced ROADMAP, requirements, metric, and session updates.
- **Files modified:** `.planning/STATE.md`
- **Verification:** Final metadata diff shows Phase 04 at 5/6 plans, 17/18 total plans, 94% progress, and stopped-at Plan 05.
- **Committed in:** final docs commit

**Total deviations:** 3 process deviations  
**Impact on plan:** Runtime behavior matches the plan. The main process impact is that overlapping pre-existing style refactor hunks in plan-target templates are included in the task commits; unrelated dirty files were preserved. The STATE correction repaired SDK metadata output.

## Issues Encountered

None blocking. The planned tests exposed the expected pre-implementation failures and passed after implementation.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None introduced. Stub scan found existing form placeholders, hidden empty input defaults, and a scores "No pick made" UI placeholder; these are live UI controls/states and do not block the plan goal.

## Threat Flags

None. No new endpoint, schema, file access, or authentication surface was introduced. The modified context processors reduce the shared template tenant leakage surface.

## Verification

- `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.Phase4SharedContextScopeTests --settings=pickem.test_settings --verbosity=2` - failed before implementation with 7 expected regression failures; passed after implementation with 7 tests.
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` - passed with 107 tests.
- `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - passed with no issues.
- `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings` - passed with `No changes detected`.
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2` - passed with 154 tests.
- `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2` - passed with 154 tests.
- `curl -s --max-time 5 http://localhost:8000 | head -40` - passed, returned public homepage HTML including `<title>Family Pick'em</title>`.

## Next Phase Readiness

Phase 04 Plan 06 can perform final cross-family negative coverage and validation handoff from a baseline where shared tenant navigation and shared context processors no longer route signed-in tenant users back to legacy private global pages or leak another family's banner/private footer stats.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/04-family-scoped-app-pages/04-05-SUMMARY.md`.
- Modified files exist: `pickem/pickem_homepage/tests.py`, `pickem/pickem/context_processors.py`, `pickem/pickem_homepage/templates/pickem/base.html`, `home.html`, `picks.html`, and `scores.html`.
- Task commits exist: `5c0a541`, `ba59c16`, and `c8ad686`.
- No tracked files were deleted by task commits.

---
*Phase: 04-family-scoped-app-pages*
*Completed: 2026-06-30*
