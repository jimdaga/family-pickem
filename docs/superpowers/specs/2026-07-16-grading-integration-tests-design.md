# Grading Engine Integration Test Suite — Design

**Date:** 2026-07-16
**Status:** Approved for implementation (user supplied requirements; deviations from the
original prompt are reconciled against the real codebase below)

## Goal

End-to-end integration tests that exercise the **real production grading pipeline** —
not unit tests of the algorithm, and no duplicated grading logic in assertions. Tests
create synthetic families, pools, users, games, and picks; populate final scores;
run the actual management commands; and assert exact standings.

## How grading actually works (ground truth)

The production pipeline is `update_all`, which runs in dependency order:

1. `update_records` / `update_games` — ESPN fetch (network; out of scope, replaced by
   synthetic game data)
2. `update_missed_picks` — applies each pool's `missed_pick_policy` (auto picks)
3. `update_picks` — pool-agnostic: flags `pick_correct` where `pick == gameWinner`
   (a team **slug**), marks games scored; real NFL ties are scored with no winner
4. `update_standings` — per (pool, user): recomputes `week_N_points` from scored picks
   using the pool's `win_points` / `tie_points`, folds in `week_N_bonus`
5. `update_weekly_winners` — once every game of the week is finished+scored, runs the
   pluggable tiebreaker engine (`pickem_api/weekly_winners.py`) per pool:
   `primary_tiebreaker` → `secondary_tiebreaker` from `PoolSettings`; combined-yards
   comes from an injectable `GameStatsProvider` (ESPN in prod)
6. `update_rankings` — per-pool competition ranking (1, 1, 3, …) into `current_rank`
7. `update_season_winners` / `update_stats` — season champion + per-user stats

**Multi-tenancy:** games are global per (season, competition) — families share the NFL
slate. Isolation lives in `GamePicks.pool`, `userSeasonPoints.pool`, and per-pool
`PoolSettings`. The original prompt's "different games per family" doesn't exist in
this schema; isolation tests assert pick/standings/rules isolation on a shared slate.

**Spread pools:** `pick_type=against_spread` is a settings enum value that is locked in
every form and has **no grading backend**. Spread scenarios cannot exercise real code
today. Instead: one live "canary" test pins the current behavior (an against_spread
pool still grades straight-up), and the four requested scenarios (favorite covers,
favorite wins without covering, underdog outright, push) are committed as
`@skip`-scaffolded tests with full expected standings, ready to enable when the
backend lands. The canary fails loudly at that moment, forcing the scaffolds on.

## Decisions

- **Django `TestCase` over pytest.** The repo has ~9k lines of Django TestCase tests,
  CI runs `manage.py test`, and there are zero test-only dependencies. Adding pytest
  buys fixtures we don't need (factories cover it) at the cost of a second idiom.
- **Hand-rolled factories over Factory Boy.** Same reasoning: `requirements.txt` is
  also the production image's dependency set (no dev-requirements split), and the
  factories needed are thin. `grading_tests/factories.py` provides Factory-Boy-style
  sensible defaults + sequences without the dependency. If the suite outgrows this,
  swapping to Factory Boy is mechanical.
- **New top-level package `pickem/grading_tests/`** (unittest discovery picks it up in
  the existing SQLite CI job automatically). Keeps the integration suite separate from
  the per-app unit tests and lets the Postgres workflow target exactly this package.
- **Real commands via `call_command`,** not direct service calls — the tests enter
  through the same door production does. The only patch: the ESPN stats provider in
  `update_weekly_winners` is replaced with a stub (the engine was explicitly designed
  for injection). `--season` is always passed so `get_season()` never hits the API.
- **Postgres in CI, SQLite locally.** New `pickem/pickem/test_settings_postgres.py`
  (extends `test_settings`, env-driven DB) + a dedicated workflow with a `postgres:16`
  service. The workflow also runs `manage.py migrate` against the service DB, so the
  full migration chain is exercised on Postgres — something the SQLite job never did.

## Layout

```
pickem/grading_tests/
    __init__.py
    README.md              # how to run, how to add a scenario
    factories.py           # family/pool/user/membership/game/pick factories
    harness.py             # pipeline runner, stub stats provider, standings asserts
    test_straight_up.py    # scenario 1 (+ tie game, missed pick, idempotency)
    test_tiebreakers.py    # scenarios 2–3 (primary, equidistant→secondary)
    test_spread_pool.py    # scenario 4 (canary + skipped scaffolds)
    test_tenant_isolation.py  # scenario 5
    test_rule_config.py    # scenario 6 (points weights, chains, missed-pick policies)
pickem/pickem/test_settings_postgres.py
.github/workflows/grading-integration-tests.yaml
```

## Key harness pieces

- `LeagueFixture` — one call creates Family + active Pool + PoolSettings (overridable)
  + N users with active memberships.
- `create_game(week, …)` / `finish_game(game, home, away)` — `finish_game` writes
  exactly what `update_games` would (scores, `gameWinner` slug, `statusType=finished`),
  so `update_picks` sees production-shaped data.
- `run_grading_pipeline(season, yards=…)` — runs `update_missed_picks`,
  `update_picks`, `update_standings`, `update_weekly_winners` (stubbed provider),
  `update_rankings` in `update_all` order.
- `assert_standings(pool, expected)` — exact-match on (user, weekly points, bonus,
  total, rank) **and** on row count, so foreign rows in a pool fail the test.

## Future scenarios (deliberately out of scope now)

- `update_season_winners` end-of-season flag
- `update_stats` accuracy/perfect-week integration
- playoff weeks (`include_playoffs` is locked/unimplemented, same treatment as spread)
