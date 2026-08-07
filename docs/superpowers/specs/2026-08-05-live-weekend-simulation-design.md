# Live Weekend Simulation Harness — Design

**Date:** 2026-08-05
**Status:** Approved (brainstorming) — pending implementation plan
**Related:** `docs/superpowers/specs/2026-08-02-live-updates-design.md` and the
phase 3b/3c SSE specs; builds on the shipped live-update feature.

## Purpose

Give a developer a single command that stands up the real live-update
infrastructure locally and replays a full, dramatized weekend of NFL games in
~5 minutes, so the SSE-driven live surfaces can be watched updating in real
time and inspected for bugs (flicker, mis-ordering, stale rows, dropped
streams, rank/avatar glitches).

This is a **dev/test tool**, not production code. It must be impossible to run
against real data or in a deployed environment.

## Success Criteria

Running `scripts/live-sim.sh` from a clean local checkout:

1. Brings up Redis + an ASGI (uvicorn) server with `REDIS_URL` set, with no
   manual steps.
2. Points the site at an isolated demo league (season 9999) that is browsable
   by the developer's real account.
3. Over ~5 minutes, drives ~13 games from `scheduled` → `live` → `final` in
   realistic waves, with scores/quarters ticking, such that:
   - `/scores` shows live score/quarter/status changes (SSE, current-season
     scoped).
   - The lobby **Week Points** panel live-reorders, and ranks/avatars appear
     as games finalize (SSE, pool scoped).
   - `/standings` live-reorders and refetches new rows (SSE, pool scoped).
   - The standings visibly shuffle mid-run and the **MNF tiebreaker flips the
     week winner** at the end.
4. On exit (normal or Ctrl-C), restores the real `currentSeason`, wipes the
   demo data, and stops uvicorn + Redis — leaving the local environment exactly
   as it was.

## Why the infra matters (constraints discovered)

- The lobby Week Points panel and `/standings` live-reorder are driven **only**
  by `EventSource`/SSE — there is no polling fallback for them
  (`family_pool_home.html` explicitly notes "no 30s poll fallback"). Therefore
  a real demo of the marquee feature **requires** working SSE:
  `REDIS_URL` set + a server that can stream (uvicorn/ASGI). Plain `runserver`
  with no Redis will not show it. (The `/scores` page does have a 30s poll
  fallback, but we drive its SSE path too.)
- The `/scores` SSE channel is `scores:{current_season}:{week}` — keyed to the
  **current season** via `get_season()`. So the demo season (9999) must be the
  current season for the run. The standings SSE channel is
  `standings:{pool_id}:{season}` — pool + its own season scoped — so it works
  for the demo pool regardless, as long as `update_standings` is invoked with
  `--season 9999`.
- `currentSeason` is a singleton read via `currentSeason.objects.first()`
  (`pickem/pickem/utils.py::get_season`). The harness updates that row's
  `season` to 9999, capturing the prior value, and restores it on teardown.

## Components

### 1. `seed_demo_weekend` management command (new)

Sibling to the existing `seed_demo_week`. Reuses its safe conventions: DEBUG
guard (refuse unless `settings.DEBUG`), season **9999**, demo family slug,
`--owner <username>` to wire a real account in as OWNER so the league is
browsable, and a `--wipe` that removes all season-9999 / demo-slug rows.

Differences from `seed_demo_week`:

- **Pre-kickoff games.** Games are seeded `statusType='scheduled'` (renamed per
  the real ESPN status vocabulary the pipeline expects — confirm exact value
  used elsewhere, e.g. `notstarted`/`scheduled`), no scores, `gameScored=False`,
  `gameWinner` empty. The simulator advances them.
- **Bigger, realistic slate.** ~13 games across one demo week with kickoff
  `startTimestamp`s spread across the compressed window, in waves:
  - 1 Thursday night game
  - ~8 Sunday early games
  - ~2 Sunday late games
  - 1 Sunday night game
  - 1 Monday night game, flagged `tieBreakerGame=True`
- **~8 fake players** (`demo-*` usernames) with `UserProfile`s carrying
  avatars/taglines/favorite team so the lobby avatar + rank rendering is
  exercised. Enough rows to trigger Week Points pagination / ScrollTrigger.
- **Scripted picks + final scores engineered for drama:** the leaderboard
  order changes at least twice during the run, and two players enter Monday
  night tied on correct picks such that the MNF result + tiebreaker guesses
  decide the week winner (flip at the end).
- Demo `Teams` rows (fake logos/colors) as `seed_demo_week` already does.

The command prints the scripted "expected outcome" (who leads at each wave, who
wins the tiebreaker) so the watcher knows what correct behavior looks like.

### 2. `simulate_weekend` management command (new — the tick engine)

DEBUG-guarded and **hard-restricted to season 9999** (refuse otherwise). This is
the clock.

Arguments:
- `--duration <seconds>` (default ~300) — total wall-clock length.
- `--speed <float>` (optional multiplier alternative to duration).
- `--tick <seconds>` (default ~1.5) — real seconds between ticks.

Model: each game has a **scripted progression** — an ordered list of states
`(t_fraction, status, home_score, away_score, period, clock)` from kickoff to
final, where `t_fraction` is the game's position within the overall window.
Kickoff waves are staggered so games overlap the way a real Sunday does.

On each tick the engine:
1. Computes elapsed fraction of the window.
2. For each game, resolves its current scripted state; if any live/publishable
   field changed since last tick, saves the `GamesAndScores` row and publishes
   via the **real production path** — reuse
   `pickem_api.live_events` (`score_event_payload` / `publish_score_event`) and
   the `maybe_publish_game_change(before, after)` helper from `update_games`, so
   the events are byte-identical to production.
3. When a game transitions to `final`, sets `gameWinner`, then runs the real
   scoring pipeline scoped to the demo season so standings SSE fires:
   `call_command('update_picks', season=9999)` then
   `call_command('update_standings', season=9999)` (and `update_weekly_winners`
   / `update_rankings --season 9999` once the week's last game is final, for the
   bonus + rank). These invoke `maybe_publish_standings_change` internally.
4. Sleeps `--tick` seconds.

It prints a running log (`[t=1:32] SNF live 14-10 Q3 · standings republished`)
so terminal + browser can be cross-checked.

Reusing the real publish + scoring paths is deliberate: the simulator's job is
to move the DB the way ESPN + the scheduler would, and let the **unchanged**
production code emit the events. It does not reimplement event formatting.

### 3. `scripts/live-sim.sh` orchestrator (new)

A bash script with a `trap … EXIT` cleanup. Steps:

**Setup**
1. Start a throwaway Redis: `docker run -d --rm -p 6379:6379 --name pickem-live-sim-redis redis:7-alpine` (name-guarded; reuse/replace if already present).
2. `export REDIS_URL=redis://localhost:6379/0`.
3. Launch the app under uvicorn: `uv run uvicorn pickem.asgi:application --host 0.0.0.0 --port 8000` (from `pickem/`), backgrounded, PID captured.
4. Poll `http://localhost:8000/healthz` until ready (timeout w/ clear error).
5. Capture the current `currentSeason.season`, then set it to 9999 (small
   inline `manage.py shell -c` or a tiny helper flag on the seeder).
6. `manage.py seed_demo_weekend --owner <username>` (username via `$1`/env, with
   a helpful prompt if missing).

**Run**
7. `manage.py simulate_weekend --duration 300` (foreground; the developer
   watches the browser meanwhile).

**Teardown (trap, runs on normal exit and Ctrl-C, idempotent)**
8. Restore the captured `currentSeason.season`.
9. `manage.py seed_demo_weekend --wipe`.
10. Kill the uvicorn PID.
11. `docker rm -f pickem-live-sim-redis`.

The script echoes the URL to open and the demo login guidance at the start.

## Data Flow (production paths, unchanged)

```
simulate_weekend
  ├─ mutate GamesAndScores ──▶ publish_score_event ──▶ Redis scores:9999:<week>
  │                                        └▶ /events/scores/ SSE ─▶ /scores page
  └─ game final ─▶ update_picks --season 9999
                    └▶ update_standings --season 9999
                         └▶ maybe_publish_standings_change ─▶ Redis standings:<pool>:9999
                                └▶ /events/standings/ SSE ─▶ lobby Week Points + /standings
```

The harness only writes DB rows and flips `currentSeason`; every event the
browser receives is produced by the real, shipped code.

## Error Handling & Safety

- **Environment guard:** both commands refuse unless `settings.DEBUG` (matches
  `seed_demo_week`). `simulate_weekend` additionally refuses any season != 9999.
- **Teardown always runs:** orchestrator `trap` restores `currentSeason` and
  wipes demo data even on Ctrl-C or mid-run failure. Teardown is idempotent so a
  second run (or a run after a crash) self-heals.
- **Redis/publish failures are already best-effort** in the production helpers
  (they never raise); the simulator inherits that. If Redis is down the sim
  still runs the DB mutations — the watcher just won't see live pushes, which is
  a visible, diagnosable state rather than a crash.
- **No collision with real data:** everything keyed to season 9999 + demo slug;
  `currentSeason` is the only shared row touched, and it is captured/restored.

## Testing

- **Unit test** (mirrors `tests/test_update_games_publish.py` and
  `tests/test_update_standings_publish.py`): run `simulate_weekend` for a few
  ticks with a tiny `--duration` against the test DB with a fake/patched Redis
  publish, and assert:
  - score events are published as games advance,
  - standings events are published when a game finalizes,
  - after the full (short) run, the demo standings reflect the scripted
    tiebreaker flip (expected week winner is correct).
- **Seeder test:** `seed_demo_weekend` creates the expected counts (family,
  pool, ~8 members, ~13 scheduled games, picks) and `--wipe` removes them all;
  DEBUG-off refuses.
- The `scripts/live-sim.sh` orchestrator (Docker/uvicorn lifecycle) is verified
  **manually** — it is environmental glue, not unit-testable logic.

## Out of Scope / YAGNI

- No configurable slate/roster via CLI beyond duration/speed — the drama is
  hard-scripted for a repeatable, known-good demo.
- No Claude-in-Chrome console/network watchdog — the developer watches solo.
- No replay of real historical weeks (explicitly rejected in favor of the
  isolated synthetic league).
- No production/deployed use — dev-only by construction.

## `statusType` vocabulary (resolved)

`statusType` is a closed set, populated only by `update_games` via `STATUS_MAP`:

- `notstarted` — pre-kickoff (ESPN `STATUS_SCHEDULED`)
- `inprogress` — live (ESPN `STATUS_IN_PROGRESS` / `STATUS_END_PERIOD` /
  `STATUS_HALFTIME`)
- `finished` — final, incl. overtime (ESPN `STATUS_FINAL` / `STATUS_FINAL_OVERTIME`)

`statusTitle` is the freeform display label ("Final", "Q3 5:22"). The simulator
scripts each game `notstarted → inprogress → finished`, matching `seed_demo_week`.

> **Follow-up (out of scope here):** `statusType` is a freeform `CharField` even
> though its value space is closed. Converting it to `models.TextChoices` would
> give admin/superadmin dropdowns + validation. Because existing values already
> conform, no data migration is needed (only a no-op `choices` migration). Worth
> doing as its own small change; deliberately **not** bundled into this harness.

## Open Questions (resolve during planning)

- Whether `update_weekly_winners` / `update_rankings` need to run every tick or
  only once at week-final; default to once-at-final to keep ticks cheap, run
  `update_standings` every finalize for the live reorder.
- Whether setting `currentSeason` is best done via a dedicated seeder flag
  (`--make-current` / restored separately) vs. inline shell in the orchestrator
  — pick the one that keeps teardown robust.
