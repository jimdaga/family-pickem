# Grading Integration Tests

End-to-end tests of the **real production grading pipeline**. Every test
creates synthetic families, pools, users, games, and picks; records final
scores the way `update_games` would; runs the actual management commands;
and asserts exact standings. No grading logic is duplicated in assertions.

## Running

```bash
cd pickem

# Fast local run (SQLite, same settings as the main CI job)
python manage.py test grading_tests --settings=pickem.test_settings

# Against PostgreSQL (what .github/workflows/grading-integration-tests.yaml runs)
DATABASE_HOST=localhost DATABASE_PORT=5432 \
DATABASE_NAME=pickem_test DATABASE_USER=postgres DATABASE_PASS=postgres \
python manage.py test grading_tests --settings=pickem.test_settings_postgres
```

## How a scenario works

```python
class MyScenario(GradingTestCase):
    def test_something(self):
        league = create_league("alice", "bob", win_points=3)   # family+pool+users
        game = create_game(1, mnf=True)                        # week 1, tiebreaker game
        make_pick(league.pool, league["alice"], game, "home", score=45)
        finish_game(game, 24, 21)                              # what update_games would write
        self.run_pipeline(yards=700)                           # the real commands
        self.assertStandings(league.pool, [(league["alice"], 3, 1), ...])
```

- `run_pipeline()` executes `update_missed_picks → update_picks →
  update_standings → update_weekly_winners → update_rankings` — the grading
  slice of production's `update_all`, in the same order. The two ESPN fetch
  steps (`update_records`, `update_games`) are replaced by the factories;
  the ESPN stats provider used by the combined-yards tiebreaker is stubbed
  via the engine's injection point (`yards=` / `per_game_yards=`).
- Production runs the pipeline every minute. Multi-week tests mirror that:
  finish a week's games, `run_pipeline()`, move to the next week —
  `update_weekly_winners` awards the latest *complete* week.
- `assertStandings` is exhaustive per pool: every standings row must be
  accounted for, so cross-tenant leakage fails even when the named users'
  numbers are right.

## Files

| File | Covers |
|---|---|
| `factories.py` | Synthetic data with production-shaped rows (winner = team slug, pick ids = `pool-user-game`) |
| `harness.py` | `GradingTestCase`: pipeline runner, stub stats provider, standings asserts |
| `test_straight_up.py` | Clear winners, NFL ties, missed picks, idempotency, week-completion gate |
| `test_tiebreakers.py` | Default chain: closest total score → closest combined yards; equidistant fall-through; co-winners; ESPN-outage deferral |
| `test_spread_pool.py` | **Canary** pinning that `against_spread` pools still grade straight-up, plus skipped scaffolds for real spread scenarios |
| `test_tenant_isolation.py` | Two families on the shared NFL slate: independent grading, standings, rules; pool-scoped recompute |
| `test_rule_config.py` | `win_points`/`tie_points`, custom bonus, every tiebreaker variant, missed-pick policies |

## The spread canary

`pick_type=against_spread` has no grading backend yet (it's locked in every
settings form). `SpreadPoolCanaryTest` asserts today's behavior — spread
pools grade straight-up. When a spread backend lands, that test fails:
delete the canary and un-skip `SpreadPoolTest`, whose scenarios (favorite
covers, favorite doesn't cover, underdog outright, push) are already written
with expected standings.

## Adding a rule type

New tiebreaker or scoring rule? Add the `PoolSettings` choice + strategy in
`pickem_api/weekly_winners.py` (see its module docstring), then add a test
here that sets the override in `create_league(...)` and asserts standings.
Nothing in the harness needs to change.

## Deliberately out of scope (future scenarios)

- `update_season_winners` (season-champion flag) and `update_stats`
  (accuracy / perfect weeks) — downstream of standings
- Playoff weeks (`include_playoffs` is locked/unimplemented, same
  treatment as spread when it lands)
