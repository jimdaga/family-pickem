# Phase 04 Validation: Family-Scoped App Pages

**Status:** Complete
**Phase goal:** Move user-facing gameplay pages into explicit tenant context.
**Nyquist result:** Every scoped behavior below is mapped to a Phase 04 plan, summary, and automated verification target.

## Plan Set

| Plan | Wave | Objective | Summary | Key Verification |
|------|------|-----------|---------|------------------|
| `04-01-PLAN.md` | 1 | Tenant dashboard/home and signed-in legacy home redirects | `04-01-SUMMARY.md` | `TenantDashboardIsolationTests`; `manage.py test pickem_homepage` |
| `04-02-PLAN.md` | 2 | Tenant picks submit/edit with server-derived fields | `04-02-SUMMARY.md` | `TenantPickFlowIsolationTests`; `manage.py test pickem_homepage` |
| `04-03-PLAN.md` | 3 | Tenant scores, standings, weekly winners, and display-only rules | `04-03-SUMMARY.md` | `TenantScoresStandingsRulesIsolationTests`; `manage.py test pickem_homepage` |
| `04-04-PLAN.md` | 4 | Tenant profiles, players, and family-private message-board AJAX | `04-04-SUMMARY.md` | `TenantProfilesPlayersMessageBoardIsolationTests`; `manage.py test pickem_homepage` |
| `04-05-PLAN.md` | 5 | Shared navigation plus dashboard/picks/scores tenant link cleanup | `04-05-SUMMARY.md` | `Phase4SharedContextScopeTests`; focused and full Django tests |
| `04-06-PLAN.md` | 6 | Remaining template link cleanup, final negative coverage, final verification/handoff | `04-06-SUMMARY.md` | `manage.py check`, migration dry-run, focused and full Django tests, curl spot-check |

## Multi-Source Coverage Audit

### GOAL Coverage

| Source Item | Coverage | Plan(s) |
|-------------|----------|---------|
| Move user-facing gameplay pages into explicit tenant context | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| Dashboard/home | COVERED | 04-01 |
| Scores | COVERED | 04-03 |
| Standings | COVERED | 04-03 |
| Picks | COVERED | 04-02 |
| Rules | COVERED | 04-03 |
| Profiles and players | COVERED | 04-04 |
| Message board | COVERED | 04-04 |
| Tenant-aware URLs and links | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| Tenant-scoped query filters for picks, standings, stats, and community content | COVERED | 04-01, 04-02, 04-03, 04-04 |
| Legacy route redirects | COVERED | 04-01, 04-02, 04-03, 04-04 |
| Cross-family page/API access is denied | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| No global pick/standing/message data appears inside a family context | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |

### REQ Coverage

| Requirement | Coverage | Plan(s) | Verification Target |
|-------------|----------|---------|---------------------|
| AUTHZ-02: Every family/pool write path checks authenticated membership server-side | COVERED | 04-02, 04-04, 04-06 | `TenantPickFlowIsolationTests`, `TenantProfilesPlayersMessageBoardIsolationTests.test_final_object_id_body_and_slug_tampering_do_not_cross_family_profiles_players_or_message_board` |
| AUTHZ-04: Outsiders cannot view or infer private family data | COVERED | 04-01, 04-03, 04-04, 04-05, 04-06 | Dashboard, scores/standings/rules, profile/player/message-board, footer/banner negative tests |
| AUTHZ-05: Client-provided tenant/user/game fields validated against server context | COVERED | 04-02, 04-06 | Pick body tampering tests plus final profile/message-board body tampering regression |
| POOL-03: Scores use global NFL facts with pool-scoped overlays | COVERED | 04-03, 04-06 | `test_tenant_scores_selected_week_uses_global_week_facts_with_pool_only_overlays` |
| POOL-04: Rules/settings visible in appropriate context | COVERED | 04-03, 04-06 | `test_tenant_rules_display_current_context_settings_and_no_editing_form`; final rules query tampering regression |
| COMM-02: Family members see profile stats only in allowed family context | COVERED | 04-04, 04-06 | `test_tenant_profile_scopes_stats_picks_posts_and_links_to_current_pool`; final profile/player slug/query tampering regression |
| SEC-03: Cross-family isolation has automated negative tests | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 | Final two-family regression suite covers dashboard, picks, scores overlays, standings, rules, profiles, players, posts, comments, votes, footer stats, and banners |
| SEC-04: Cache keys and precomputed data are family/pool scoped | COVERED | 04-01, 04-03, 04-05, 04-06 | Dashboard/standings scoped query tests and footer stats scoped/suppressed tests |

### RESEARCH Coverage

| Research Finding | Coverage | Plan(s) |
|------------------|----------|---------|
| Use existing Django function views and `family_member_required` | COVERED | 04-01, 04-02, 04-03, 04-04 |
| Keep NFL games/weeks/teams global | COVERED | 04-01, 04-02, 04-03 |
| Scope private overlays by `pool` and community rows by `family` | COVERED | 04-01, 04-02, 04-03, 04-04 |
| Redirect signed-in legacy private routes before rendering global data | COVERED | 04-01, 04-02, 04-03, 04-04 |
| Derive pick write fields server-side | COVERED | 04-02 |
| Use scoped object lookup for message-board and profile IDs | COVERED | 04-04 |
| No package installs are needed | COVERED | all plans |
| Keep UI edits focused during Bootstrap-to-Tailwind migration | COVERED | all template plans |

### CONTEXT Decision Coverage

| Decision | Coverage | Plan(s) |
|----------|----------|---------|
| D-01 tenant URLs | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| D-02 legacy signed-in redirects | COVERED | 04-01, 04-02, 04-03, 04-04 |
| D-03 no private global signed-in legacy rendering | COVERED | 04-01, 04-02, 04-03, 04-04 |
| D-04 auth and membership required for private surfaces | COVERED | 04-01, 04-02, 04-03, 04-04 |
| D-05 global NFL reference data | COVERED | 04-01, 04-02, 04-03 |
| D-06 pool-scoped pick overlays | COVERED | 04-02, 04-03 |
| D-07 server-derived pick fields | COVERED | 04-02 |
| D-08 scores do not leak other pools | COVERED | 04-03, 04-05, 04-06 |
| D-09 tenant dashboard scoped data | COVERED | 04-01 |
| D-10 remove/rewrite global dashboard widgets | COVERED | 04-01 |
| D-11 standings and weekly winners current-pool scoped | COVERED | 04-03 |
| D-12 scoped cache/precomputed data | COVERED | 04-01, 04-03, 04-05, 04-06 |
| D-13 family-private players/profiles/posts/comments/votes | COVERED | 04-04 |
| D-14 active family membership for profile/player viewing | COVERED | 04-04 |
| D-15 profile/stat views scoped to current family/pool | COVERED | 04-04 |
| D-16 message-board AJAX family/pool scoped | COVERED | 04-04 |
| D-17 cross-family negative tests | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| D-18 tenant-aware rules | COVERED | 04-03 |
| D-19 no rules/settings editing | COVERED | 04-01, 04-03 |
| D-20 static fallback rules display allowed | COVERED | 04-03 |
| D-21 tenant-preserving links | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| D-22 tenant-local empty states | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| D-23 non-leaking denial behavior | COVERED | 04-01, 04-03, 04-04, 04-05, 04-06 |
| D-24 mobile/header context remains visible | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |

## Final Negative Test Evidence

| Surface | Tampering Covered | Automated Evidence |
|---------|-------------------|--------------------|
| Dashboard widgets | Direct tenant URL slug tampering; cross-family seeded standings, picks, posts, and members | `TenantDashboardIsolationTests.test_dashboard_scopes_private_widgets_to_current_family_and_pool`; `test_direct_tenant_dashboard_requires_membership` |
| Pick reads/writes | URL slug tampering, cross-pool pick ID tampering, and request body tenant/user/game/correctness tampering | `TenantPickFlowIsolationTests.test_outsider_cannot_get_or_post_tenant_picks_by_url_slug_tampering`; `test_cross_pool_pick_id_edit_is_denied_before_lock_or_team_validation`; `test_tenant_post_creates_server_derived_pick_and_ignores_forged_fields` |
| Scores overlays | Query tampering and selected-week pool overlay isolation while global NFL game facts still render | `TenantScoresStandingsRulesIsolationTests.test_tenant_scores_selected_week_uses_global_week_facts_with_pool_only_overlays`; `test_final_slug_query_and_overlay_tampering_do_not_cross_family_scores_standings_or_rules` |
| Standings and weekly winners | Query tampering, cross-family rows/winners, and tenant profile links | `TenantScoresStandingsRulesIsolationTests.test_tenant_standings_and_weekly_winners_are_current_pool_only`; `Phase4SharedContextScopeTests.test_final_standings_rules_profile_footer_and_banner_links_preserve_tenant_context` |
| Rules | Query tampering and display-only current-pool settings | `TenantScoresStandingsRulesIsolationTests.test_tenant_rules_display_current_context_settings_and_no_editing_form`; `test_final_slug_query_and_overlay_tampering_do_not_cross_family_scores_standings_or_rules` |
| Players and profile stats | Direct slug tampering, query tampering, target-user membership checks, scoped points/picks/posts/stats | `TenantProfilesPlayersMessageBoardIsolationTests.test_tenant_players_list_contains_only_current_family_active_members`; `test_tenant_profile_scopes_stats_picks_posts_and_links_to_current_pool`; `test_final_object_id_body_and_slug_tampering_do_not_cross_family_profiles_players_or_message_board` |
| Posts, comments, and votes | Object ID tampering and request body family/pool tampering for create/comment/vote/read AJAX | `TenantProfilesPlayersMessageBoardIsolationTests.test_tenant_create_comment_denies_cross_family_post_and_parent_ids_generically`; `test_tenant_vote_post_and_comment_deny_cross_family_ids_generically`; `test_tenant_get_comments_serializes_only_current_family_post_comments`; `test_final_object_id_body_and_slug_tampering_do_not_cross_family_profiles_players_or_message_board` |
| Shared footer stats | Cross-pool stored rank/current-week pick counts and no-safe-pool suppression | `Phase4SharedContextScopeTests.test_footer_stats_context_scopes_private_stats_to_current_pool`; `test_footer_stats_context_suppresses_private_stats_without_safe_pool`; `test_final_standings_rules_profile_footer_and_banner_links_preserve_tenant_context` |
| Family banners | Current-family banner selection, site-wide fallback, and other-family banner exclusion | `Phase4SharedContextScopeTests.test_site_banner_context_does_not_show_another_family_banner_on_tenant_page`; `test_site_banner_context_allows_site_wide_banner_when_current_family_has_none`; `test_final_standings_rules_profile_footer_and_banner_links_preserve_tenant_context` |

## Out-of-Scope Guardrails

| Item | Status |
|------|--------|
| Family settings/rules editing forms | NOT CLAIMED; remains Phase 5 |
| Invite management, revocation/regeneration UI, role/member management | NOT CLAIMED; remains Phase 5 |
| Family admin editing | NOT CLAIMED; remains Phase 5 |
| Cron/scoring job production hardening | NOT CLAIMED; remains Phase 6 |
| Production migration backup/rollback/non-null hardening | NOT CLAIMED; remains Phase 6 |
| Multi-active-pool UI | NOT PLANNED |

## Final Verification Checklist

- [x] `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` - PASS, no issues.
- [x] `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings` - PASS, `No changes detected`.
- [x] `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2` - PASS, 157 tests.
- [x] `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2` - PASS, 157 tests.
- [x] `curl -s --max-time 5 http://localhost:8000 | head -40` - PASS, public homepage HTML returned with `<title>Family Pick'em</title>`.

## Completion Evidence

| Evidence | Status | Reference |
|----------|--------|-----------|
| Dashboard/home summary | COMPLETE | `04-01-SUMMARY.md` |
| Picks summary | COMPLETE | `04-02-SUMMARY.md` |
| Scores/standings/rules summary | COMPLETE | `04-03-SUMMARY.md` |
| Profiles/message-board summary | COMPLETE | `04-04-SUMMARY.md` |
| Link cleanup summary | COMPLETE | `04-05-SUMMARY.md` |
| Final verification summary | COMPLETE | `04-06-SUMMARY.md` |

## Phase 04 Handoff

Phase 04 completes tenant-scoped user-facing gameplay pages and cross-family negative coverage. It does not complete family admin editing, invite/role management UI, cron/scoring job hardening, CSRF hardening beyond the migrated routes, or production migration hardening. Those remain explicitly assigned to later phases.
