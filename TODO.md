# Project Name
Pickem

## To Do

#### Infra & Maintenance (July 2026)
- [~] Fix release automation end-to-end. Done 2026-07-10: (1) `publish_helm` was racing the main-branch `-latest` workflow on the `gh-pages` index push — both chart-releaser jobs now share a `concurrency: helm-chart-release` group and use `skip_existing: true` for idempotent re-runs. (2) Added an **app-of-apps** root Application (`infra/argocd/applications/root-app.yaml`) that watches `infra/argocd/applications/` with `automated` sync + `selfHeal` + `prune`, so a git change to a child app (e.g. the release workflow bumping `pickem-prd`'s targetRevision) now reconciles to the live cluster automatically — the manual `kubectl apply -f pickem-prd.yaml` step is retired. Bootstrapped once with `kubectl apply -f root-app.yaml`; self-managing after that. The **workflow → git** half is wired but needs a secret: `update_argocd` now checks out with `token: ${{ secrets.ARGOCD_PUSH_TOKEN }}` so its push authenticates as the token owner. **ACTION REQUIRED:** create a fine-grained PAT owned by a repo admin (jimdaga) with Contents: Read/Write on `family-pickem`, add it as the Actions secret `ARGOCD_PUSH_TOKEN`. Because this repo is user-owned with `enforce_admins=false`, an admin-owned PAT bypasses the protected-branch PR requirement, so the push lands on main and the app-of-apps root auto-reconciles prd. (`github-actions` can't be a bypass actor on the classic protection API — HTTP 500 — hence the PAT.)
- [ ] Run DB migrations in an initContainer instead of inline in `docker-entrypoint.sh`. Today `manage.py migrate` runs before the server starts in the same container, so long migrations get SIGKILLed by the liveness probe and it takes multiple restarts to finish (seen on the 0.0.135 prd rollout, exit 137). Move migrate (and collectstatic) into an initContainer in `charts/family-pickem/templates/deployment.yaml` — probes then only ever see a fully-migrated app container.
- [x] Cut a GitHub Release to bump prd off chart `0.0.118-latest`. ~~Picks up the backup-cronjob password fix~~ Done 2026-07-06: released 0.0.135, prd rolled, manual backup job verified in S3. ~~Note for next release: prd Application manifests are NOT app-of-apps managed — after the workflow commits the targetRevision bump, someone must `kubectl apply -f infra/argocd/applications/pickem-prd.yaml`.~~ Superseded 2026-07-10: prd Application manifests are now app-of-apps managed via the root Application, so the manual `kubectl apply` is no longer needed after the targetRevision bump lands on main.
- [ ] Remove the `update-data` CronJob from the chart entirely — the scheduler is now live in dev+prd (0.0.135) and the CronJob is suspended in both. After a couple of clean weeks of `update_all` job runs, delete the cronjob template/values and the legacy `cron_*.py` scripts.
- [ ] Decide on migrating pickemctl into Django scheduled tasks (recommended): ~6 aggregate queries writing to `userStats`, would retire the separate repo, Docker image, K8s deployment, and pickemctl ESO secret. Raw SQL there has already broken once from Django column renames.
- [ ] pickemctl: branch `refactor/cleanup-phase-1` in ~/git/pickemctl (4 commits, unpushed) — module rename, removed committed 12MB binary, deduped topPicked/leastPicked, extracted pickStats query helpers. Push/PR it, or drop it if the Django migration proceeds.

#### Multi-Family / Tenant Follow-Up Backlog

##### Ideas
- [ ] Build a season-rollover flow: a commissioner action (or scheduled task) that creates the next season's pool for each family, marks it default, and seeds `GameWeeks` from the ESPN calendar, and copies the prior pool's `PoolSettings` forward (fresh defaults on the 2627 pool made saved rules look lost — settings are per-pool). For 2026/27 this was done manually via Django shell in prd (2026-07-06: created `pickem-pool` season 2627, demoted `2526-pickem`, inserted 126 GameWeeks rows) — that recipe should become code.
- [x] Make the "Live Scores" shortcut jump directly to active game cards when games are live. Consider using an anchor or query parameter on the scores page so users land on the most relevant game instead of the top of the page.
- [x] Make more of the rules page editable by family admins. Decide which rules are true settings versus display-only copy before exposing edit controls.
- [ ] Clarify how submitting picks should work for users in multiple families. Confirm whether one pick submission can apply to multiple pools, or whether picks must always be submitted independently per family/pool.
- [ ] Give families a way to set and manage a logo. Include validation for image URL/upload, fallback behavior, and admin-only authorization.
- [ ] Move invites toward an email-based model. Hide or de-emphasize raw invite codes once email invites are available.
- [ ] Automate email reminders for missing picks. Reminders must be family/pool scoped and should respect notification preferences.
- [ ] Rebase this work from upstream `main` and resolve merge conflicts carefully, especially around the frontend refactor and multi-tenant schema changes.
- [ ] Add end-to-end tests for critical flows: sign in, create/join family, switch family, submit picks, view scores/standings, and cross-family isolation.
- [x] Rename/reframe the main pool page as a "Lobby". Update the top-left logo behavior so it links to the public homepage, while internal navigation has a separate family/pool home affordance.
- [ ] Evaluate whether a global user points page should exist. If added, define what is global versus family-scoped so it does not leak private pool data.
- [ ] Add a "Confidence points" pick type (rank picks 1-16 each week; correct picks earn their rank). Popular on ESPN/Yahoo. Big scoring-logic lift — pick type setting already exists, so this becomes a third option alongside straight-up and against-the-spread.
- [ ] Implement the logic behind the new pool rule settings: against-the-spread scoring, missed-pick auto-assignment, playoff continuation, late-join enforcement, and tiebreaker automation. Settings exist and display on the rules page; the scorer/joins need to consume them.

##### Fixes
- [ ] Fix the Submit Picks page so users can clearly see picks they already submitted. Recheck whether edit-before-lock still works after the multi-family changes.
- [ ] Move banner management into its own focused admin tool/page instead of burying it in broader admin controls.
- [x] Remove non-SSO username/password login from the visible login flow for now. Login pages should route to a single login page first, not directly to Google, so future auth providers can be added cleanly.
- [ ] Restore editing and commenting on message board posts. Ensure all actions are family-scoped and protected by membership checks.
- [ ] Add pagination or incremental loading for message board posts so family lobbies do not become too heavy.
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



- [ ] Write script to use ESPNs calendar data to populate the weeks:
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
