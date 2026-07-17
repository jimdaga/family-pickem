# Family Pickem — TODO

Audited 2026-07-17: every code-related open item below was verified against
the current code (manual infra chores, like the AWS Secrets Manager cleanup,
can't be — they're marked as manual). Finished and stale items are collapsed
under **Done** at the bottom.

## Active Backlog

### Features

- [ ] **Season-rollover flow.** A commissioner action (or scheduled task) that
  creates the next season's pool for each family, marks it default, seeds
  `GameWeeks` from the ESPN calendar (see reference at the bottom), and copies
  the prior pool's `PoolSettings` forward (settings are per-pool, so fresh
  defaults make saved rules look lost). For 2026/27 this was done manually via
  Django shell in prd (2026-07-06: created `pickem-pool` season 2627, demoted
  `2526-pickem`, inserted 126 GameWeeks rows) — that recipe should become code.
  Verified 2026-07-17: still no rollover/calendar code anywhere.
- [ ] **Implement playoff support (`PoolSettings.include_playoffs`)** — the
  setting exists but is disabled in the admin settings form ("coming soon",
  `disabled=True`) because nothing downstream supports postseason play. Scope
  when picking this up: (1) `userSeasonPoints` only has
  `week_1..18_{points,bonus,winner}` columns — needs schema (weeks 19-22 or a
  normalized per-week table); (2) every pipeline command hardcodes
  `range(1, 19)` (`update_standings.WEEKS`, `weekly_winners._recompute_total`,
  `update_stats.WEEK_WINNER_FIELDS`, `update_season_winners.FINAL_WEEK`);
  (3) `update_games`/`GameWeeks` need postseason week fetching (ESPN
  `seasontype=3`); (4) picks/scores/standings pages assume weeks 1-18
  (`week_choices = range(1, 19)`); (5) `update_season_winners` must wait for
  the configured final week (SB for playoff pools, wk18 otherwise);
  (6) re-enable the form field + rules-page copy. Ideally lands together with
  the season-rollover flow above.
- [ ] **Against-the-spread scoring** (`pick_type=against_spread`, locked
  "coming soon" in both settings forms). When it lands: unlock the form
  fields, delete the `SpreadPoolCanaryTest` in `pickem/grading_tests/`, and
  un-skip `SpreadPoolTest` there — the four spread scenarios (favorite
  covers / wins-without-covering / underdog outright / push) are already
  written with expected standings.
- [ ] **Confidence points pick type** (rank picks 1-16 each week; correct
  picks earn their rank). Verified 2026-07-17: not started — no ranking
  scoring logic exists.
- [ ] **Automate email reminders for missing picks.** Verified 2026-07-17:
  not started, no reminder code anywhere. Must be family/pool scoped and
  respect notification preferences. Resend delivery infrastructure now
  exists (`pickem_homepage/emailing.py`), so this is mostly scheduling +
  templates.
- [ ] **Hide raw invite codes once email invites are the norm.** The rest of
  the email-invite model is done (see Done); the admin UI still shows raw
  codes/links as the fallback for pools without Resend configured.

### Chores

- [ ] Delete the now-unused `family-pickem/{prd,dev}/pickemctl` entries in
  AWS Secrets Manager (manual cleanup, left over from the pickemctl
  retirement).

## Done

Recently completed (verified 2026-07-17):

- [x] **Give commissioners a way to "delete" a family** — soft delete only:
  the owner types the exact family name in a Danger Zone on admin Settings;
  `Family.status` flips to inactive (data fully preserved), tenant pages 404,
  invites stop working, the update pipeline skips the family, and the
  superadmin Families page can reactivate it.
- [x] **Make the Create Family flow more involved** — the create page now
  requires the full pool-rules form inline (prefilled with defaults, same
  validation as admin Settings) and one-email-per-row invites that create
  real targeted invitations (emailed via Resend when configured).
- [x] Default pool names no longer embed the season ("Pick'em Pool"); a data
  migration renamed existing season-suffixed defaults that doubled up in
  page headers.
- [x] **End-to-end grading integration tests** (PR #72):
  `pickem/grading_tests/` runs the real pipeline commands against synthetic
  tenants (straight-up, tiebreaker chains, tenant isolation, rule config)
  plus a dedicated PostgreSQL GitHub Actions workflow. Critical user flows
  (sign in, create/join family, picks, admin) are covered by the Django
  test suite; no browser-level E2E planned.
- [x] **Release automation is fully hands-off** — chart-releaser concurrency
  + `skip_existing`, app-of-apps root Application, migrations in an
  initContainer, and the `ARGOCD_PUSH_TOKEN` fine-grained PAT (in place and
  proven: 0.0.168/0.0.169 shipped merge → release → prd with zero manual
  steps). Reminder: release tags MUST be `family-pickem-X.Y.Z`.
- [x] **Email-based invites** — `FamilyInvitation.recipient_email` targeting,
  case-insensitive redemption match, Resend delivery with branded templates
  (0.0.166, restyled 0.0.169), and invite-link 500 fixes.
- [x] **Security & bug audit follow-ups (2026-07-11)** — all deferred
  findings fixed: admin manual-pick lock check, csrf_exempt removal, strict
  boolean profile settings, case-insensitive username checks, tenant-scoped
  profile stats, read-only vestigial DRF endpoints, trimmed `GamePicksForm`,
  SRI-pinned chart.js, tiebreaker latching, `update_records` off the 1-minute
  pipeline, `json_script` theme handoff, scores-page re-entrancy guard.
- [x] Superadmin console, pickemctl → Django migration, `update_all`
  pipeline, banners admin, message-board edit/delete/pagination,
  multi-family pick submission, family logos, global leaderboard, lobby
  reframe, live-scores shortcut, editable rules page, "Pickem Pool" default
  names, family-switcher create action, submitted-picks visibility.

<details>
<summary>Legacy done list (pre-multi-tenant era)</summary>

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

</details>

<details>
<summary>Reference: ESPN calendar API shape for the season-rollover GameWeeks-seeding item</summary>

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
