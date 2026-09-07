# Automatic tiebreaker-game selection

**Date:** 2026-09-07

## Problem

`GamesAndScores.tieBreakerGame` marks the one game per week on which players
enter their score/yards predictions. Nothing in the data pipeline writes it —
it is set by hand in Django admin every week, and it gets forgotten. A week
with no flagged game shows no tiebreaker inputs on `/picks/`, so a weekly tie
cannot be settled on predictions.

## Goal

Every week automatically carries exactly one tiebreaker game: the last game of
the week (normally Monday night). Week 18 is the exception until its kickoff
times are published.

## Rule

For each `(gameseason, gameWeek, competition)` group:

1. Order the group's games by `startTimestamp` descending.
2. **If two or more games tie for the latest kickoff, skip the group entirely**
   and log why. Existing flags are left as they are — a week we cannot reason
   about is a week we do not touch.
3. Otherwise the single latest game is the tiebreaker: `tieBreakerGame=True` on
   it, `False` on every other game in the group.

### Why the tie rule instead of a week-18 special case

Until the week-18 schedule firms up, ESPN returns every week-18 game at one
shared placeholder kickoff. Verified against the live scoreboard for the 2026
season: all 16 week-18 games return `2027-01-10T05:00Z`. There is therefore no
identifiable last game, and the tie test detects that state directly.

Two consequences of expressing it this way:

- It covers any week ESPN has not finalized, not only week 18.
- It releases itself the moment real kickoff times land — no date logic, no
  manual unlock.

A rule keyed on "kickoff is at midnight" would be wrong: the placeholder is
midnight *Eastern* (`05:00Z`), not midnight UTC.

## Authority

The automation is authoritative. Every run enforces exactly one flagged game
per non-skipped group, clearing any other flags found. A flex-scheduled game
that stops being last is corrected on the next tick, as is a bad manual flag.
A deliberate manual override does not survive.

There is **no kickoff freeze** — the flag is enforced whether or not the week
is underway. Accepted consequence: if ESPN corrects a kickoff time mid-weekend
such that a different game becomes last, the flag moves after picks lock, and
predictions already entered sit on the old game. `WeekContext.prediction`
(`pickem_api/weekly_winners.py`) then finds nothing and the week falls through
to `missing_tiebreaker_actual`, resolving via the pool's secondary tiebreaker
(split points / coin flip) instead of via predictions.

## Implementation

### New command: `pickem_api/management/commands/update_tiebreakers.py`

Core function, importable so tests do not go through `call_command`:

```python
def set_week_tiebreaker(season, week, competition) -> GamesAndScores | None
```

Returns the flagged game, or `None` when the group was skipped or empty.

- Idempotent: a group already in the correct state performs zero writes.
- Writes use queryset `.update()`, so a no-op run does not churn `gameUpdated`.
- Competitions are grouped separately, matching `WeekContext`, which filters by
  `pool.competition`.

Command arguments:

- `--season` — YYZZ, defaults to `get_season()`.
- `--week` — defaults to today's week via `current_week_for_today`, reused from
  `update_games`.
- `--all-weeks` — every week present for the season. This is the backfill path.
- `--dry-run` — report what would change without writing.

### Pipeline

Inserted into `update_all.PIPELINE` between `update_games` (which supplies the
kickoff times the rule reads) and `update_missed_picks`. `update_all` forwards
`--season` to every step, so the command must accept it.

Added to `pickem_superadmin/jobs.QUEUEABLE_COMMANDS` so it can be queued from
`/superadmin/jobs/`.

## Tests

`pickem_api/tests/test_update_tiebreakers.py`:

- Last game of a normal week is flagged.
- A pre-existing flag on the wrong game is cleared.
- A group whose games all share the latest kickoff is left completely untouched,
  including any flag already present.
- A single-game group flags that game.
- A second run over correct data performs no writes.
- Two competitions in the same week each get their own tiebreaker.
- `--all-weeks` covers every week of the season.

## Rollout

After merge, backfill the season once:

```bash
python manage.py update_tiebreakers --season <YYZZ> --all-weeks --dry-run
python manage.py update_tiebreakers --season <YYZZ> --all-weeks
```

From then on the pipeline maintains it.
