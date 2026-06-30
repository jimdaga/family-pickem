---
phase: 04-family-scoped-app-pages
plan: 04
subsystem: family-scoped-app-pages
tags: [django, multi-tenancy, profiles, players, message-board, ajax, security, tests]

requires:
  - phase: 01-domain-schema-foundation
    provides: nullable family scope on message-board rows and nullable pool scope on picks, standings, and user stats
  - phase: 02-authorization-foundation
    provides: active family/pool membership authorization helpers and browser route guard
  - phase: 04-family-scoped-app-pages
    provides: tenant dashboard, picks, scores, standings, and rules routes from Plans 01-03
provides:
  - Family-private tenant profile and player routes under explicit family/pool URLs
  - Pool-scoped profile points, picks, ranks, team-pick stats, and userStats reads
  - Family-scoped message-board create/comment/vote/read AJAX endpoints with generic cross-family JSON failures
  - Cross-family negative tests for players, profiles, stats, posts, comments, votes, and AJAX serialization
affects: [shared-navigation-cleanup, final-family-scoped-validation, family-admin, production-migration]

tech-stack:
  added: []
  patterns:
    - Resolve viewed profile users through active FamilyMembership in request.tenant_context.family before reading profile data
    - Use request.tenant_context.pool for profile competition stats and request.tenant_context.family for community rows
    - Keep legacy signed-in profile access as a redirect bridge and legacy message-board AJAX as generic JSON not-found

key-files:
  created:
    - pickem/pickem_homepage/templates/pickem/players.html
  modified:
    - pickem/pickem_homepage/views.py
    - pickem/pickem_homepage/urls.py
    - pickem/pickem_homepage/templates/pickem/family_pool_home.html
    - pickem/pickem_homepage/templates/pickem/user_profile_private.html
    - pickem/pickem_homepage/tests.py

key-decisions:
  - "Tenant profile pages return 404 unless the viewed user has an active membership in the current family."
  - "Profile privacy is evaluated only after tenant membership is proven, so privacy cannot substitute for family authorization."
  - "Legacy signed-in profile URLs redirect into the resolved tenant profile route; legacy message-board AJAX returns generic JSON not-found instead of writing family-null private rows."
  - "Tenant dashboard message-board endpoint URLs are rendered server-side from the current family/pool context."

patterns-established:
  - "Family-private user surfaces should resolve target users through FamilyMembership before reading UserProfile, GamePicks, userSeasonPoints, userStats, or message-board rows."
  - "Message-board AJAX handlers should delegate through family-scoped core helpers and catch Http404 as a generic JSON not-found."
  - "Tenant dashboard templates should expose route URLs from Django reverse/url tags instead of hardcoded global AJAX paths."

requirements-completed: [AUTHZ-02, AUTHZ-04, COMM-02, SEC-03, SEC-04]

coverage:
  - id: D1
    description: "Tenant player lists contain only active members of the current family."
    requirement: COMM-02
    verification:
      - kind: unit
        ref: "pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests.test_tenant_players_list_contains_only_current_family_active_members"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tenant profile views require active current-family membership for the viewed user and scope profile stats/picks/posts to current pool/family."
    requirement: AUTHZ-04
    verification:
      - kind: unit
        ref: "pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests.test_tenant_profile_scopes_stats_picks_posts_and_links_to_current_pool"
        status: pass
      - kind: unit
        ref: "pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests.test_tenant_profile_requires_target_user_current_family_membership"
        status: pass
      - kind: unit
        ref: "pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests.test_outsider_direct_tenant_profiles_and_players_are_denied"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tenant message-board create/comment/vote/read AJAX derives family server-side and does not serialize or mutate cross-family IDs."
    requirement: AUTHZ-02
    verification:
      - kind: unit
        ref: "pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests.test_tenant_create_post_assigns_current_family_server_side"
        status: pass
      - kind: unit
        ref: "pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests.test_tenant_create_comment_denies_cross_family_post_and_parent_ids_generically"
        status: pass
      - kind: unit
        ref: "pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests.test_tenant_vote_post_and_comment_deny_cross_family_ids_generically"
        status: pass
      - kind: unit
        ref: "pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests.test_tenant_get_comments_serializes_only_current_family_post_comments"
        status: pass
    human_judgment: false
  - id: D4
    description: "Tenant dashboard markup exposes tenant message-board endpoint URLs instead of hardcoded legacy global AJAX paths."
    requirement: SEC-04
    verification:
      - kind: unit
        ref: "pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests.test_tenant_homepage_message_board_uses_tenant_ajax_urls_only"
        status: pass
    human_judgment: false

duration: 46min
completed: 2026-06-30
status: complete
---

# Phase 04 Plan 04: Family-Private Profiles Players And Message Board Summary

**Family-private profiles, player lists, and message-board AJAX with tenant-scoped profile stats and generic cross-family JSON failures.**

## Performance

- **Duration:** 46min
- **Started:** 2026-06-30T00:29:15Z
- **Completed:** 2026-06-30T01:15:34Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added tenant player and profile routes under `/families/<family_slug>/pools/<pool_slug>/`.
- Scoped profile target resolution to active current-family membership before reading profile details.
- Scoped profile points, rank calculations, recent picks, team-pick chart data, and user stats to the current pool.
- Scoped profile message counts to the current family.
- Added tenant message-board AJAX endpoints for post creation, comment creation, post voting, comment voting, and comment reads.
- Derived message-board `family` server-side and used family-scoped lookups for every post/comment/vote mutation and serialization path.
- Added cross-family IDOR tests proving URL slug, request body, object ID, and serialization tampering do not expose another family.

## Task Commits

1. **Task 1: Add profile players and message-board negative tests** - `a6ea986` (test)
2. **Task 2: Implement tenant profiles and players** - `c9684a7` (feat)
3. **Task 3: Implement tenant message-board AJAX** - `03471f8` (feat)

## Files Created/Modified

- `pickem/pickem_homepage/templates/pickem/players.html` - New tenant player list for active current-family members.
- `pickem/pickem_homepage/views.py` - Added tenant profile/player views, pool/family profile scoping, tenant message-board AJAX handlers, and generic legacy AJAX denial.
- `pickem/pickem_homepage/urls.py` - Added tenant player, profile, and message-board AJAX route names.
- `pickem/pickem_homepage/templates/pickem/family_pool_home.html` - Added server-rendered tenant message-board endpoint URLs.
- `pickem/pickem_homepage/templates/pickem/user_profile_private.html` - Keeps private-profile back navigation inside tenant context when available.
- `pickem/pickem_homepage/tests.py` - Added profile/player/message-board positive and cross-family negative coverage.

## Decisions Made

- Kept anonymous legacy profile behavior available, but redirected signed-in legacy profile requests to tenant context before private data reads.
- Returned generic `{"success": false, "error": "Not found"}` with 404 for cross-family message-board IDs and legacy message-board AJAX access.
- Used the existing `family_pool_home.html` tenant dashboard as the endpoint source for tenant message-board URLs because signed-in root requests no longer render legacy `home.html`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tightened brittle cross-family tests**
- **Found during:** Task 2 and Task 3 verification
- **Issue:** Two negative assertions matched incidental response content rather than the security property: a 404 body assertion expected a 200 response body, and a digit-only JSON search collided with timestamps/user IDs.
- **Fix:** Changed those assertions to verify response status, scoped context values, and serialized comment IDs directly.
- **Files modified:** `pickem/pickem_homepage/tests.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `c9684a7`, `03471f8`

**2. [Rule 2 - Missing Critical Functionality] Denied legacy message-board AJAX writes**
- **Found during:** Task 3
- **Issue:** The plan focused on adding tenant AJAX routes, but leaving signed-in legacy AJAX endpoints writing family-null posts/comments/votes would preserve a private-data bypass.
- **Fix:** Converted legacy message-board AJAX handlers to return generic JSON 404 and implemented tenant-only handlers that derive and enforce `family=request.tenant_context.family`.
- **Files modified:** `pickem/pickem_homepage/views.py`
- **Verification:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2`
- **Committed in:** `03471f8`

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical functionality)
**Impact on plan:** Both fixes directly support the plan's family-private security boundary and do not add unrelated scope.

## Issues Encountered

- A combined verification command attempted `cd pickem` twice, so the second check command hit `zsh: no such file or directory: ../venv/bin/python`. The Django check was rerun separately from the repository root and passed.

## User Setup Required

None - no external service configuration required.

## Known Stubs

- `pickem/pickem_homepage/views.py:1045` contains a pre-existing `TODO` in score/week winner logic. It was present outside this plan's profile/player/message-board changes and does not block this plan's family-private profile or message-board goals.

## Threat Flags

None - the new route/AJAX trust boundaries match the plan threat model entries T-04-08, T-04-09, and T-04-10.

## Verification

- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests --settings=pickem.test_settings --verbosity=2` — 11 tests passed.
- PASS: `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` — 100 tests passed.
- PASS: `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` — no issues.
- PASS: `curl -s --max-time 5 http://localhost:8000 | head -40` — public homepage returned HTML.
- NOTE: A first Task 1 red run of `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` produced 11 `NoReverseMatch` errors for the not-yet-implemented tenant route names; this was expected coverage confirmation before Tasks 2-3.

## Next Phase Readiness

Phase 04 Plan 05 can continue with shared navigation, context processor, and tenant-link cleanup. Profiles, player lists, and message-board AJAX now have explicit tenant route names and negative cross-family coverage for Plan 06 validation.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/04-family-scoped-app-pages/04-04-SUMMARY.md`.
- Created template exists at `pickem/pickem_homepage/templates/pickem/players.html`.
- Modified files exist: `views.py`, `urls.py`, `family_pool_home.html`, `user_profile_private.html`, and `tests.py`.
- Task commits exist: `a6ea986`, `c9684a7`, and `03471f8`.
- No tracked file deletions were introduced by task commits.

---
*Phase: 04-family-scoped-app-pages*
*Completed: 2026-06-30*
