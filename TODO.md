# Project Name
Pickem

## To Do

#### Infra & Maintenance (July 2026)
- [~] Fix release automation end-to-end. Done 2026-07-10: (1) `publish_helm` was racing the main-branch `-latest` workflow on the `gh-pages` index push — both chart-releaser jobs now share a `concurrency: helm-chart-release` group and use `skip_existing: true` for idempotent re-runs. (2) Added an **app-of-apps** root Application (`infra/argocd/applications/root-app.yaml`) that watches `infra/argocd/applications/` with `automated` sync + `selfHeal` + `prune`, so a git change to a child app (e.g. the release workflow bumping `pickem-prd`'s targetRevision) now reconciles to the live cluster automatically — the manual `kubectl apply -f pickem-prd.yaml` step is retired. Bootstrapped once with `kubectl apply -f root-app.yaml`; self-managing after that. The **workflow → git** half is wired but needs a secret: `update_argocd` now checks out with `token: ${{ secrets.ARGOCD_PUSH_TOKEN }}` (confirmed present in `.github/workflows/publish-artifacts.yaml`) so its push authenticates as the token owner. **ACTION REQUIRED (manual, not code):** create a fine-grained PAT owned by a repo admin (jimdaga) with Contents: Read/Write on `family-pickem`, add it as the Actions secret `ARGOCD_PUSH_TOKEN`. Because this repo is user-owned with `enforce_admins=false`, an admin-owned PAT bypasses the protected-branch PR requirement, so the push lands on main and the app-of-apps root auto-reconciles prd. (`github-actions` can't be a bypass actor on the classic protection API — HTTP 500 — hence the PAT.)
- [x] Run DB migrations in an initContainer instead of inline in `docker-entrypoint.sh`. Done 2026-07-11: `docker-entrypoint.sh` now branches on `$1 = migrate` to run collectstatic + makemigrations + migrate and exit, instead of doing it unconditionally before `runserver`. `charts/family-pickem/templates/deployment.yaml` gained an `initContainers:` block (`{{ .Chart.Name }}-migrate`, same image, `args: ["migrate"]`) that runs before the main container starts, so the liveness probe never sees a mid-migration app again.
- [ ] Delete the now-unused `family-pickem/{prd,dev}/pickemctl` entries in AWS Secrets Manager (manual cleanup, left over from the pickemctl retirement below).
- [x] Add `Teams.logo_contrast_preset` editing to the future superadmin page so team-brand contrast fixes do not require Django admin access. Done 2026-07-14: the `/superadmin/teams/` page edits `logo_contrast_preset` and team colors inline, with a live preview swatch rendering the logo on its brand background.
- [x] Cut a GitHub Release to bump prd off chart `0.0.118-latest`. ~~Picks up the backup-cronjob password fix~~ Done 2026-07-06: released 0.0.135, prd rolled, manual backup job verified in S3. ~~Note for next release: prd Application manifests are NOT app-of-apps managed — after the workflow commits the targetRevision bump, someone must `kubectl apply -f infra/argocd/applications/pickem-prd.yaml`.~~ Superseded 2026-07-10: prd Application manifests are now app-of-apps managed via the root Application, so the manual `kubectl apply` is no longer needed after the targetRevision bump lands on main.
- [x] Remove the `update-data` CronJob from the chart entirely. Done 2026-07-10: deleted `templates/cronjob.yaml`, the `cron:` values blocks (chart defaults + prd/dev), `cron.sh`, and all legacy `cron_*.py` scripts. The APScheduler `update_all` pipeline replaces them (verified running cleanly in prd). ArgoCD prunes the suspended CronJob on sync.
- [x] Migrate pickemctl into Django. Done 2026-07-10: new `update_stats` management command (`pickem_api/management/commands/update_stats.py`) reimplements pickemctl's userStats aggregation in the ORM (accuracy, weeks/seasons won, missed picks, perfect weeks, most/least picked — season + all-time, one global pool-null row per user). Added to the `update_all` pipeline. Removed the pickemctl deployment/secret/external-secret chart templates and the `pickemctl:` + `pickemctlKey` values. ArgoCD prunes the deployment on sync. The AWS Secrets Manager `family-pickem/{prd,dev}/pickemctl` entries are now unused and can be deleted at leisure.
- [x] ~~pickemctl repo branch `refactor/cleanup-phase-1`~~ — moot; pickemctl retired (see above). The ~/git/pickemctl repo/image can be archived.

#### Security & Bug Audit Follow-Ups (2026-07-11)

Deferred lower-severity findings from the full audit. The critical/major ones (anonymous cross-tenant pick/points/PII leaks in the DRF API, cookie hardening, ESPN tie/OT/null-overwrite data-integrity bugs) were fixed in the audit PR; these remain:
- [x] **Admin manual-pick tool has no lock/kickoff check** (`family_pool_admin_picks`, `views.py` ~1671): fixed 2026-07-11 by applying `is_pick_locked_for_pool` to admin manual-pick writes so locked/in-progress/finished games reject retroactive edits.
- [x] **`toggle_theme` and `check_username` are `@csrf_exempt`** state-changing/oracle POST endpoints; `check_username` also returns `str(e)` and is a username-existence oracle. Fixed 2026-07-11: dropped `@csrf_exempt`, kept CSRF protection, and switched both endpoints to generic error responses; `check_username` no longer reveals availability.
- [x] **Profile AJAX settings store raw JSON values** (`private_profile`/`dark_mode`/`email_notifications`) with no boolean coercion — `{"value":"false"}` stores truthy string, silently leaving a profile public. Fixed 2026-07-11: settings now coerce strict booleans and reject invalid payloads without echoing raw exceptions.
- [x] **Profile username uniqueness check is case-sensitive + active-only** while the DB constraint is global — a case-variant or an inactive user's name passes the app check then 500s on save. Fixed 2026-07-11: validation now uses `username__iexact` across all users and save handles `IntegrityError`.
- [x] **`render_user_profile` anonymous path uses global unscoped querysets** (`userSeasonPoints.objects.all()`, `GamePicks.objects.all()`) — leaks a public-profile user's cross-family aggregate stats/picks to anonymous visitors. Fixed 2026-07-11 by removing anonymous profile detail access entirely; profile detail remains tenant-scoped for signed-in users.
- [x] **Destructive API writes still global + staff-only** (`game_list`/`week_list` DELETE run `objects.all().delete()`). Fixed 2026-07-11 by making the vestigial games/weeks DRF endpoints read-only and removing the write/delete surface.
- [x] **`GamePicksForm` (forms.py) exposes `userID`/`uid`/`userEmail`/`pick_correct`** as bindable fields — inert today (never bound to request data) but a mass-assignment footgun one line from being live. Fixed 2026-07-11 by trimming the form to pick/tiebreaker fields only.
- [x] **`chart.js`/`chartjs-plugin-datalabels` on user_profile.html lack SRI and chart.js is version-unpinned** — fixed 2026-07-11 by pinning both CDN assets and adding SRI + `crossorigin="anonymous"`.
- [x] **weekly_winners tiebreaker latching**: fixed 2026-07-11 so missing tiebreaker actuals (e.g. ESPN `combined_yards` blips) do not latch co-winners, split bonuses preserve the full configured total, and `--force` reruns zero non-winner bonuses instead of nulling them.
- [x] **`scheduler` runs `update_records` (33 sequential 30s-timeout ESPN calls) inline in the 1-minute pipeline** — fixed 2026-07-11 by moving records refresh onto its own slower APScheduler cadence and having the 1-minute pipeline skip that step.
- [x] **base.html interpolates `user_theme_preference` raw into an inline `<script>` string** — fixed 2026-07-11 by switching the backend theme handoff to `json_script`.
- [x] **scores.html `startLiveUpdates()` has no re-entrancy guard** — fixed 2026-07-11 by guarding `updateInterval`, resetting it on shutdown, and de-duping the visibility-change listener before re-arming.

#### Multi-Family / Tenant Follow-Up Backlog

##### Ideas
- [ ] Build a season-rollover flow: a commissioner action (or scheduled task) that creates the next season's pool for each family, marks it default, seeds `GameWeeks` from the ESPN calendar (see snippet below — still nothing implemented, no `calendar` references anywhere in `pickem/**/*.py`), and copies the prior pool's `PoolSettings` forward (fresh defaults on the 2627 pool made saved rules look lost — settings are per-pool). For 2026/27 this was done manually via Django shell in prd (2026-07-06: created `pickem-pool` season 2627, demoted `2526-pickem`, inserted 126 GameWeeks rows) — that recipe should become code. **Audited 2026-07-11: still not started**, no management command exists.
- [x] Make the "Live Scores" shortcut jump directly to active game cards when games are live. Consider using an anchor or query parameter on the scores page so users land on the most relevant game instead of the top of the page.
- [x] Make more of the rules page editable by family admins. Decide which rules are true settings versus display-only copy before exposing edit controls.
- [x] Clarify how submitting picks should work for users in multiple families. **Done, audited 2026-07-11**: `get_multi_family_pick_target_pools`/`get_multi_family_pick_target_choices` (`pickem_homepage/views.py:437-496`) plus `apply_to_all_families`/`target_pool_ids` handling (`views.py:2995-3024`) let one submission apply to multiple pools via a checkbox in `picks.html:731-744`.
- [x] Give families a way to set and manage a logo. Done 2026-07-11: `logo_url` is now a field on `FamilyAdminSettingsForm` (`pickem_homepage/forms.py`) editable from the user-facing family settings page (admin-only, same `family_pool_admin_settings` view/auth as the rest of the form), with a `clean_logo_url` validator that accepts a full `https://` URL or a site-relative `/...` path and rejects anything else. The lobby hero (`family_pool_home.html`) already had a default-logo fallback for an unset URL; added an `onerror` handler so a set-but-broken URL also falls back to the default logo client-side. Changes are audit-logged. Upload (vs. URL-only) was not in scope.
- [~] Move invites toward an email-based model. **Updated 2026-07-16:** `FamilyInvitation` now supports an optional `recipient_email`, admin invite creation can target that address, invite redemption enforces a case-insensitive email match, and the admin UI now emphasizes the invite link over the raw code. **Still outstanding:** actual send-invite-email delivery and fully hiding raw codes once that exists.
- [ ] Automate email reminders for missing picks. **Audited 2026-07-11: not started**, no "reminder" code anywhere in `pickem/**/*.py`. Must be family/pool scoped and respect notification preferences.
- [ ] Rebase this work from upstream `main` and resolve merge conflicts carefully, especially around the frontend refactor and multi-tenant schema changes.
- [ ] Add end-to-end tests for critical flows: sign in, create/join family, switch family, submit picks, view scores/standings, and cross-family isolation.
- [x] Rename/reframe the main pool page as a "Lobby". Update the top-left logo behavior so it links to the public homepage, while internal navigation has a separate family/pool home affordance.
- [x] Evaluate whether a global user points page should exist. **Done, audited 2026-07-11**: `global_leaderboard` view (`pickem_homepage/views.py:2302-2382`) at `/leaderboard/` blends `userSeasonPoints`/`userStats` across all pools per user, exposing only username/points/accuracy/leagues-count — no pool names or private data leaked.
- [ ] Add a "Confidence points" pick type (rank picks 1-16 each week; correct picks earn their rank). **Audited 2026-07-11: not started** — `PoolSettings.PickType` (`models.py:185-187`) still only has `STRAIGHT_UP` and `AGAINST_SPREAD` ("coming soon"); no ranking scoring logic exists.
- [~] Implement the logic behind the new pool rule settings. **Mostly done 2026-07-13**: `win_points`/`tie_points` now drive `update_standings`; `missed_pick_policy` is enforced by the new `update_missed_picks` pipeline step (auto picks flagged `GamePicks.auto_pick`, excluded from userStats accuracy/perfect-weeks); `late_join_policy` blocks new members at invite acceptance once Week 1 completes; `allow_tiebreaker` gates the pick-page tiebreaker inputs; the new `update_season_winners` step writes `year_winner`; the manual weekly-winner override uses the pool's `weekly_winner_points` instead of a hardcoded 2. `payout_structure`/`entry_fee`/`perfect_week_bonus` are intentionally display-only (cash settled outside the app; perfect weeks surfaced on the admin Winners page). **Still outstanding:** against-the-spread scoring (form-blocked "coming soon") and playoff continuation (see dedicated playoffs item below).
- [ ] **Implement playoff support (`PoolSettings.include_playoffs`)** — the setting exists but is disabled in the admin settings form ("coming soon", `disabled=True` in `FamilyAdminSettingsForm`) because nothing downstream supports postseason play. Scope when picking this up: (1) `userSeasonPoints` only has `week_1..18_{points,bonus,winner}` columns — needs schema (weeks 19-22 or a normalized per-week table); (2) every pipeline command hardcodes `range(1, 19)` (`update_standings.WEEKS`, `weekly_winners._recompute_total`, `update_stats.WEEK_WINNER_FIELDS`, `update_season_winners.FINAL_WEEK`); (3) `update_games`/`GameWeeks` need postseason week fetching (ESPN `seasontype=3`); (4) picks/scores/standings pages assume weeks 1-18 (`week_choices = range(1, 19)`); (5) `update_season_winners` must wait for the configured final week (SB for playoff pools, wk18 otherwise); (6) re-enable the form field + rules-page copy. Ideally lands together with the season-rollover flow above.

- [ ] Give commissioners a way to "delete" a family — as a **soft delete only**. Mark the family inactive (an `is_active`/`status` flag on `Family`); never destroy member/pick/standings/message data. The UI must make the consequence unmistakable (clear warning copy about what deactivation does and does not do) and require the commissioner to **type the exact family name to confirm** before the action runs — same confirm-by-typing pattern as the superadmin current-season change. Decide inactive-family behavior when scoping: hidden from the family switcher/lobby, blocks new picks/joins, but all data retained so it can be reactivated. Should also surface in the superadmin families page.
- [~] Make the "Create Family" flow more involved so people are less likely to create a family just for fun. **Updated 2026-07-16:** the create-family form now includes a placeholder field for invitee emails, captured/ignored for now so the flow starts steering toward intentional setup. **Still outstanding:** require the full `PoolSettings` form inline during signup instead of silent defaults.

##### Fixes
- [x] Fix the Submit Picks page so users can clearly see picks they already submitted, with edit-before-lock working. **Done, audited 2026-07-11**: `render_pick_page` passes `pick_slugs`/`pick_ids` (`views.py:2918-2920`); `picks.html:118-120,384-484` highlights submitted picks and shows an edit button wired to `edit_game_pick`/`tenant_edit_game_pick` (`views.py:3056,3062`) with lock-checking via `is_pick_locked_for_pool`.
- [x] Move banner management into its own focused admin tool/page instead of burying it in broader admin controls. Done 2026-07-11: split `manage_banner`/`deactivate_banner` out of `family_pool_admin_settings` into a new `family_pool_admin_banners` view/URL/template (`family_admin_banners.html`), added a "Banners" card to the admin hub and a link from the Settings page header. Settings page no longer renders the publish form or banner list (the site-wide active-banner strip via `site_banner_context` is unrelated and still shows everywhere, as before).
- [x] Remove non-SSO username/password login from the visible login flow for now. Login pages should route to a single login page first, not directly to Google, so future auth providers can be added cleanly.
- [x] Restore editing and commenting on message board posts. Done 2026-07-11: added `edit_post`/`delete_post`/`edit_comment`/`delete_comment` views (tenant + legacy-404-stub pattern matching the rest of the message board), family-scoped and permission-checked (edit = author only, delete = author or family owner/admin via `is_family_moderator`). Wired into `family_messages.html` with inline edit forms and confirm-before-delete.
- [x] Add pagination or incremental loading for message board posts. **Done, audited 2026-07-11**: `tenant_messages` (`views.py:3612-3628`) uses `django.core.paginator.Paginator(posts_qs, 15)`.
- [x] Refactor all update scripts for family/pool awareness. Revisit whether these should become Django management commands/tasks instead of standalone API-calling cron scripts.
- [x] Change default pool names to "Pickem Pool".
- [x] Add a "Create new family" action inside the family switcher so multi-family users have an obvious path to add another family.

## Done 
- [x] Add % win likely 
- [x] Finish writing tool to generate stats
- [x] For past seasons show the winner at the top
- [x] Allow editing picks before they lock 
- [x] Fullscreen tiebreaker should be a new line so it doesn't overflow
- [x] Fix place circle to be top left 
- [x] Make picks lock at 1PM Sat (add "locked" to game?)
- [x] Give users way to change username (remove dependency on username in points)
- [x] Add "Favorite Team"
- [x] Add "Tagline" and update League Member 
- [x] Implement "Edit" button 
- [x] Add phone numbers to users 
- [x] Fix alignment so LIVE doesn't make scores not line up 
- [x] Make live/final/upcoming buttons work 
- [x] Show box score on mobile
- [x] Make site live refresh 
- [x] Ensure team record shows
- [x] Update prod instance with weeks/games for 2023/24
- [x] Fix records to use current season
- [x] Add 'season' logic to picks
- [x] Update scores page to be aware of year/season 
- [x] Refactor score updates to use ESPN api
- [x] Link to ESPN team logos (https://a.espncdn.com/i/teamlogos/nfl/500/ne.png)
- [x] Add "winner" to each week's page 
- [x] Home team not getting scores (1-4) after game ends
- [x] Automate teams win/losses 
- [x] Update `GameScored` in pick update 
- [x] Script to update correct picks (http://localhost:8000/api/unscored)
- [x] Fix "active games" api
- [x] Add tie breaker 
- [x] Add per quarter scores 
- [x] Update wins/losses logic for teams 
- [x] Cronjobs to run all background scripts 
- [x] fix navbar dropdowns (bootstrap javascript issue?)
- [x] fix navbar hiding things
- [x] Deploy to AWS w/ RDS 
- [x] Inprogress Pick pills not showing on scores page 
- [x] rules page 
- [x] Show submitted "tie breaker" on picks page 
- [x] Recollect all the game data (for each week, update)

<details>
<summary>Reference: ESPN calendar API shape for the season-rollover GameWeeks-seeding item above</summary>

```
                    "label": "Regular Season",
                    "value": "2",
                    "startDate": "2025-09-04T07:00Z",
                    "endDate": "2026-01-08T07:59Z",
                    "entries": [
                        {
                            "label": "Week 1",
                            "alternateLabel": "Week 1",
                            "detail": "Sep 4-9",
                            "value": "1",
                            "startDate": "2025-09-04T07:00Z",
                            "endDate": "2025-09-10T06:59Z"
                        },
```

</details>
