# Automatic Tiebreaker-Game Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every week automatically carries exactly one `tieBreakerGame` — the last game of the week — set by the data pipeline instead of by hand, and skipped for weeks whose kickoff times ESPN has not yet published (week 18).

**Architecture:** A new Django management command `update_tiebreakers` operates purely on already-stored `GamesAndScores` rows (no ESPN calls). Its core is a plain function `set_week_tiebreaker(season, week, competition)` so tests can call it directly without `call_command`. The command is inserted into the `update_all` pipeline right after `update_games`, and added to the superadmin job allowlist.

**Tech Stack:** Django 5.2 management commands, Django ORM, `django.test.TestCase`, Python 3.12, run with `uv`.

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-09-07-auto-tiebreaker-game-design.md`.
- Working directory for every command below is `/Users/jim/git/family-pickem/pickem` (the Django project root, where `manage.py` lives). Note `git add` paths are written repo-relative, so run git from the repo root or adjust.
- Branch `feat/auto-tiebreaker-game` already exists and is checked out. Do not create another.
- `GamesAndScores.gameWeek` is a **`CharField`**, not an integer. Always filter and compare weeks as `str(...)`.
- `GamesAndScores.gameseason` is an **integer** in `YYZZ` form (e.g. `2627`). Always filter with `int(...)`.
- The grouping key is `(gameseason, gameWeek, competition)` — never season+week alone.
- Writes use queryset `.update()`, never `Model.save()`, so an unchanged run does not churn the `auto_now` `gameUpdated` column.
- The command must be idempotent: an already-correct group performs zero writes.
- Run tests with: `uv run python manage.py test <label> --settings=pickem.test_settings`
- Every commit message ends with:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EKQvoUBZ6qDWj5YsRS8nY7
  ```

## File Structure

- **Create** `pickem/pickem_api/management/commands/update_tiebreakers.py` — the whole feature: the selection rule (`_week_games`, `_last_game`), the public `set_week_tiebreaker` / `preview_week_tiebreaker` functions, the `weeks_for_season` / `competitions_for_week` helpers, and the `Command` wrapper. One file, matching every sibling in that directory (`update_games.py`, `update_missed_picks.py`), which each hold their own helpers plus `Command`.
- **Create** `pickem/pickem_api/tests/test_update_tiebreakers.py` — all tests for the above, matching the sibling test modules in `pickem_api/tests/`.
- **Modify** `pickem/pickem_api/management/commands/update_all.py` — add the step to `PIPELINE` and to the module docstring's ordered list.
- **Modify** `pickem/pickem_superadmin/jobs.py` — add `'update_tiebreakers'` to `QUEUEABLE_COMMANDS`.
- **Modify** `CLAUDE.md` — the pipeline order documented under "Data Pipeline & Automated Updates".

---

### Task 1: The selection rule

**Files:**
- Create: `pickem/pickem_api/management/commands/update_tiebreakers.py`
- Test: `pickem/pickem_api/tests/test_update_tiebreakers.py`

**Interfaces:**
- Consumes: `pickem_api.models.GamesAndScores`; the existing test factory `grading_tests.factories.create_game`.
- Produces:
  - `set_week_tiebreaker(season, week, competition) -> int | None` — flags the single latest-kickoff game in the group, clears the flag on every other game in that group, and returns the flagged game's **id**. Returns `None` when the group is empty or when two or more games tie for the latest kickoff, in which case **nothing is written at all**.
  - `_week_games(season, week, competition) -> list[dict]` and `_last_game(games, season, week, competition) -> dict | None` — internal, but Task 2 reuses both.

**Background for the implementer:**

`GamesAndScores.tieBreakerGame` is a boolean marking the one game per week on which players enter score/yards tiebreaker predictions (consumed by `WeekContext.tiebreaker_game` in `pickem_api/weekly_winners.py`). Nothing in the pipeline currently writes it — it is set by hand in Django admin and gets forgotten.

Until ESPN publishes week-18 kickoff times, it returns every week-18 game at one shared placeholder timestamp (verified against the live scoreboard: all 16 games at `2027-01-10T05:00Z`). That is why the skip condition is "two or more games tie for the latest kickoff" rather than anything mentioning week 18 or midnight — the placeholder is midnight *Eastern*, not midnight UTC, so an hour check would be wrong.

The test factory lives at `pickem/grading_tests/factories.py`. Its exact signature — note `week` is positional and everything after it is keyword-only:

```python
create_game(week, *, season=2526, home=None, away=None, kickoff=None,
            mnf=False, tiebreaker_game=None, home_win_probability=None,
            away_win_probability=None, spread=None)
```

Two behaviours to guard against: when `tiebreaker_game` is `None` it silently copies `mnf`, and when `kickoff` is `None` it derives one from an internal sequence counter. **Always pass both `tiebreaker_game=` and `kickoff=` explicitly** in these tests so the starting state and the ordering are unambiguous. Every game it creates uses `competition="nfl"`.

- [ ] **Step 1: Write the failing tests**

Create `pickem/pickem_api/tests/test_update_tiebreakers.py`:

```python
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from grading_tests.factories import create_game
from pickem_api.management.commands.update_tiebreakers import set_week_tiebreaker
from pickem_api.models import GamesAndScores

SEASON = 2627


class SetWeekTiebreakerTests(TestCase):
    def setUp(self):
        self.base = timezone.now() - timedelta(days=30)

    def _game(self, week, hours_after_base, flagged=False):
        return create_game(
            week,
            season=SEASON,
            kickoff=self.base + timedelta(hours=hours_after_base),
            tiebreaker_game=flagged,
        )

    def _flagged_ids(self, week):
        return set(
            GamesAndScores.objects.filter(
                gameseason=SEASON, gameWeek=str(week), tieBreakerGame=True
            ).values_list("id", flat=True)
        )

    def test_flags_last_game_of_week(self):
        self._game(1, 0)
        self._game(1, 3)
        mnf = self._game(1, 30)

        self.assertEqual(set_week_tiebreaker(SEASON, 1, "nfl"), mnf.id)
        self.assertEqual(self._flagged_ids(1), {mnf.id})

    def test_clears_flag_from_wrong_game(self):
        stale = self._game(2, 0, flagged=True)
        mnf = self._game(2, 30)

        set_week_tiebreaker(SEASON, 2, "nfl")

        stale.refresh_from_db()
        mnf.refresh_from_db()
        self.assertFalse(stale.tieBreakerGame)
        self.assertTrue(mnf.tieBreakerGame)

    def test_tied_latest_kickoff_leaves_week_untouched(self):
        # ESPN's unpublished-schedule state: every game shares one placeholder
        # kickoff, so there is no identifiable last game.
        a = self._game(18, 5)
        b = self._game(18, 5, flagged=True)

        self.assertIsNone(set_week_tiebreaker(SEASON, 18, "nfl"))

        a.refresh_from_db()
        b.refresh_from_db()
        self.assertFalse(a.tieBreakerGame)
        # The pre-existing flag survives: a week we cannot reason about is a
        # week we do not touch.
        self.assertTrue(b.tieBreakerGame)

    def test_single_game_week_is_flagged(self):
        only = self._game(3, 0)

        self.assertEqual(set_week_tiebreaker(SEASON, 3, "nfl"), only.id)
        only.refresh_from_db()
        self.assertTrue(only.tieBreakerGame)

    def test_empty_week_returns_none(self):
        self.assertIsNone(set_week_tiebreaker(SEASON, 9, "nfl"))

    def test_second_run_writes_nothing(self):
        self._game(4, 0)
        mnf = self._game(4, 30)

        set_week_tiebreaker(SEASON, 4, "nfl")

        # One SELECT and no writes: the group is already correct.
        with self.assertNumQueries(1):
            self.assertEqual(set_week_tiebreaker(SEASON, 4, "nfl"), mnf.id)

        self.assertEqual(self._flagged_ids(4), {mnf.id})

    def test_competitions_are_grouped_separately(self):
        nfl_late = self._game(5, 30)
        self._game(5, 0)
        other_early = self._game(5, 0)
        other_late = self._game(5, 29)
        GamesAndScores.objects.filter(
            id__in=[other_early.id, other_late.id]
        ).update(competition="ncaa")

        self.assertEqual(set_week_tiebreaker(SEASON, 5, "nfl"), nfl_late.id)
        self.assertEqual(set_week_tiebreaker(SEASON, 5, "ncaa"), other_late.id)
        self.assertEqual(self._flagged_ids(5), {nfl_late.id, other_late.id})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run python manage.py test pickem_api.tests.test_update_tiebreakers --settings=pickem.test_settings
```
Expected: FAIL — `ModuleNotFoundError: No module named 'pickem_api.management.commands.update_tiebreakers'`.

- [ ] **Step 3: Write the selection rule**

Create `pickem/pickem_api/management/commands/update_tiebreakers.py`:

```python
"""Flag the last game of each week as that week's tiebreaker game.

``GamesAndScores.tieBreakerGame`` marks the one game per week on which players
enter score/yards tiebreaker predictions (see ``pickem_api/weekly_winners.py``).
It used to be set by hand every week and was easy to forget, leaving a week with
no tiebreaker inputs at all.

The rule: within a ``(gameseason, gameWeek, competition)`` group, the game with
the strictly latest kickoff is the tiebreaker — normally Monday night.

If two or more games tie for the latest kickoff, the group is skipped entirely
and left exactly as it was. That is the week-18 guard: until the schedule firms
up, ESPN returns every week-18 game at one shared placeholder kickoff, so there
is no identifiable last game. Expressing it as a tie test rather than a week-18
special case means it also covers any other unfinalized week, and it releases
itself the moment real kickoff times land. A kickoff-hour check would be wrong
here -- the placeholder is midnight *Eastern*, not midnight UTC.

The selection is authoritative: every run clears stray flags, so a
flex-scheduled game that stops being last corrects itself. There is deliberately
no kickoff freeze; see the design doc for the accepted trade-off.

Runs from the update pipeline immediately after ``update_games``, which is what
supplies the kickoff times this reads.
"""

import logging

from django.core.management.base import BaseCommand

from pickem.utils import get_season
from pickem_api.models import GamesAndScores
from pickem_api.management.commands.update_games import current_week_for_today

logger = logging.getLogger(__name__)


def _week_games(season, week, competition):
    """One group's games, latest kickoff first. One query, values only."""
    return list(
        GamesAndScores.objects.filter(
            gameseason=int(season),
            gameWeek=str(week),
            competition=competition,
        )
        .order_by("-startTimestamp")
        .values("id", "startTimestamp", "tieBreakerGame")
    )


def _last_game(games, season, week, competition):
    """The single latest-kickoff game, or None when there is no unique one."""
    if not games:
        return None
    latest = games[0]["startTimestamp"]
    tied = sum(1 for game in games if game["startTimestamp"] == latest)
    if tied > 1:
        logger.info(
            "Skipping tiebreaker for season %s week %s (%s): %d games tie for "
            "the latest kickoff %s -- schedule not published yet",
            season, week, competition, tied, latest,
        )
        return None
    return games[0]


def set_week_tiebreaker(season, week, competition):
    """Flag the last game of one (season, week, competition) group.

    Returns the flagged game's id, or None when the group is empty or has no
    strictly-latest game -- in which case nothing is written.
    """
    games = _week_games(season, week, competition)
    target = _last_game(games, season, week, competition)
    if target is None:
        return None

    stale_ids = [game["id"] for game in games[1:] if game["tieBreakerGame"]]
    if stale_ids:
        GamesAndScores.objects.filter(id__in=stale_ids).update(tieBreakerGame=False)
    if not target["tieBreakerGame"]:
        GamesAndScores.objects.filter(id=target["id"]).update(tieBreakerGame=True)
    return target["id"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
uv run python manage.py test pickem_api.tests.test_update_tiebreakers --settings=pickem.test_settings
```
Expected: PASS, 7 tests.

If `test_second_run_writes_nothing` fails on the query count, wrap the call in
`django.test.utils.CaptureQueriesContext` and print the captured SQL to find the
extra query — an already-correct group must issue only the single `SELECT` from
`_week_games`.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/management/commands/update_tiebreakers.py \
        pickem/pickem_api/tests/test_update_tiebreakers.py
git commit -m "$(cat <<'EOF'
feat(pipeline): select each week's tiebreaker game automatically

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EKQvoUBZ6qDWj5YsRS8nY7
EOF
)"
```

---

### Task 2: Management command wrapper

**Files:**
- Modify: `pickem/pickem_api/management/commands/update_tiebreakers.py`
- Test: `pickem/pickem_api/tests/test_update_tiebreakers.py`

**Interfaces:**
- Consumes: `_week_games`, `_last_game`, `set_week_tiebreaker` from Task 1; `current_week_for_today(season) -> str` from `pickem_api/management/commands/update_games.py` (already imported in Task 1's module header); `pickem.utils.get_season() -> int`.
- Produces:
  - `preview_week_tiebreaker(season, week, competition) -> int | None` — the id the tiebreaker *would* be set to, writing nothing.
  - `weeks_for_season(season) -> list[str]` — distinct `gameWeek` values present for a season, ordered numerically.
  - `competitions_for_week(season, week) -> list[str]` — distinct competitions present in one season+week.
  - The `update_tiebreakers` management command, accepting `--season`, `--week`, `--all-weeks`, `--dry-run`.

**Background for the implementer:**

`update_all` invokes each pipeline step as `call_command(name, season=season)` when a season was supplied, so this command **must** accept `--season`. Follow `update_games.py`'s `Command.handle` for the house pattern: resolve `season` from the option or `get_season()`, resolve `week` from the option or `current_week_for_today(season)`, then write progress to `self.stdout`.

`gameWeek` is a `CharField` holding `"1"`..`"18"`, so a plain sort orders `"10"` before `"2"`. Sort with `int()`, and tolerate a non-numeric value rather than raising — a junk row must not take down a pipeline step.

- [ ] **Step 1: Write the failing tests**

Append to `pickem/pickem_api/tests/test_update_tiebreakers.py`:

```python
from io import StringIO
from unittest import mock

from django.core.management import call_command

from pickem_api.management.commands import update_tiebreakers as ut


class WeeksForSeasonTests(TestCase):
    def setUp(self):
        self.base = timezone.now() - timedelta(days=30)

    def test_orders_weeks_numerically_not_lexically(self):
        for week in (2, 10, 1):
            create_game(week, season=SEASON, kickoff=self.base, tiebreaker_game=False)

        self.assertEqual(ut.weeks_for_season(SEASON), ["1", "2", "10"])

    def test_other_seasons_are_excluded(self):
        create_game(1, season=SEASON, kickoff=self.base, tiebreaker_game=False)
        create_game(7, season=2526, kickoff=self.base, tiebreaker_game=False)

        self.assertEqual(ut.weeks_for_season(SEASON), ["1"])


class CommandTests(TestCase):
    def setUp(self):
        self.base = timezone.now() - timedelta(days=30)

    def _week(self, week, hours):
        return [
            create_game(
                week,
                season=SEASON,
                kickoff=self.base + timedelta(hours=h),
                tiebreaker_game=False,
            )
            for h in hours
        ]

    def test_defaults_to_current_week(self):
        last = self._week(6, [0, 1, 30])[-1]

        with mock.patch.object(ut, "current_week_for_today", return_value="6"):
            call_command("update_tiebreakers", season=SEASON, stdout=StringIO())

        last.refresh_from_db()
        self.assertTrue(last.tieBreakerGame)

    def test_explicit_week_only_touches_that_week(self):
        week6_last = self._week(6, [0, 30])[-1]
        week7_last = self._week(7, [0, 30])[-1]

        call_command("update_tiebreakers", season=SEASON, week="7", stdout=StringIO())

        week6_last.refresh_from_db()
        week7_last.refresh_from_db()
        self.assertFalse(week6_last.tieBreakerGame)
        self.assertTrue(week7_last.tieBreakerGame)

    def test_all_weeks_covers_every_week(self):
        week6_last = self._week(6, [0, 30])[-1]
        week7_last = self._week(7, [0, 30])[-1]

        call_command(
            "update_tiebreakers", season=SEASON, all_weeks=True, stdout=StringIO()
        )

        week6_last.refresh_from_db()
        week7_last.refresh_from_db()
        self.assertTrue(week6_last.tieBreakerGame)
        self.assertTrue(week7_last.tieBreakerGame)

    def test_dry_run_writes_nothing(self):
        last = self._week(8, [0, 30])[-1]
        out = StringIO()

        call_command(
            "update_tiebreakers", season=SEASON, week="8", dry_run=True, stdout=out
        )

        last.refresh_from_db()
        self.assertFalse(last.tieBreakerGame)
        self.assertIn("would flag", out.getvalue().lower())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run python manage.py test pickem_api.tests.test_update_tiebreakers --settings=pickem.test_settings
```
Expected: FAIL — `AttributeError: module 'pickem_api.management.commands.update_tiebreakers' has no attribute 'weeks_for_season'`, and `CommandError: Unknown command: 'update_tiebreakers'` (the module exists but has no `Command` class yet).

- [ ] **Step 3: Add the preview and enumeration helpers**

Append to `pickem/pickem_api/management/commands/update_tiebreakers.py`, after
`set_week_tiebreaker`:

```python
def preview_week_tiebreaker(season, week, competition):
    """The id the tiebreaker would be set to, writing nothing. None if skipped."""
    games = _week_games(season, week, competition)
    target = _last_game(games, season, week, competition)
    return target["id"] if target else None


def weeks_for_season(season):
    """Distinct gameWeek values for a season, ordered numerically.

    gameWeek is a CharField, so a database sort would put "10" before "2".
    Non-numeric weeks sort last rather than raising -- a junk row must not take
    down a pipeline step.
    """
    weeks = set(
        GamesAndScores.objects.filter(gameseason=int(season))
        .values_list("gameWeek", flat=True)
    )
    return sorted(
        weeks,
        key=lambda w: (
            not str(w).isdigit(),
            int(w) if str(w).isdigit() else 0,
            str(w),
        ),
    )


def competitions_for_week(season, week):
    """Distinct competitions present in one (season, week)."""
    return sorted(
        set(
            GamesAndScores.objects.filter(
                gameseason=int(season), gameWeek=str(week)
            ).values_list("competition", flat=True)
        )
    )
```

- [ ] **Step 4: Add the Command class**

Append to the same file:

```python
class Command(BaseCommand):
    help = "Flag the last game of each week as that week's tiebreaker game."

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, default=None)
        parser.add_argument(
            "--week", default=None, help="Week number (defaults to today's week)."
        )
        parser.add_argument(
            "--all-weeks",
            action="store_true",
            help="Process every week present for the season (use for backfills).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        dry_run = options["dry_run"]

        if options["all_weeks"]:
            weeks = weeks_for_season(season)
        else:
            weeks = [str(options["week"] or current_week_for_today(season))]

        self.stdout.write(
            f"Setting tiebreaker games for season {season} "
            f"week(s) {', '.join(weeks) or '(none)'}"
        )

        flagged = 0
        for week in weeks:
            for competition in competitions_for_week(season, week):
                if dry_run:
                    game_id = preview_week_tiebreaker(season, week, competition)
                else:
                    game_id = set_week_tiebreaker(season, week, competition)

                if game_id is None:
                    self.stdout.write(
                        f" - week {week} ({competition}): skipped, no single last game"
                    )
                    continue

                flagged += 1
                verb = "would flag" if dry_run else "tiebreaker ="
                self.stdout.write(
                    f" - week {week} ({competition}): {verb} game {game_id}"
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run -- nothing written."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Set tiebreaker for {flagged} week/competition group(s)."
                )
            )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```bash
uv run python manage.py test pickem_api.tests.test_update_tiebreakers --settings=pickem.test_settings
```
Expected: PASS, 13 tests.

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_api/management/commands/update_tiebreakers.py \
        pickem/pickem_api/tests/test_update_tiebreakers.py
git commit -m "$(cat <<'EOF'
feat(pipeline): add update_tiebreakers command with --all-weeks backfill

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EKQvoUBZ6qDWj5YsRS8nY7
EOF
)"
```

---

### Task 3: Wire into the pipeline and the superadmin job allowlist

**Files:**
- Modify: `pickem/pickem_api/management/commands/update_all.py` (module docstring lines 7-18, `PIPELINE` lines 28-39)
- Modify: `pickem/pickem_superadmin/jobs.py` (`QUEUEABLE_COMMANDS`, lines 21-33)
- Test: `pickem/pickem_api/tests/test_update_tiebreakers.py`

**Interfaces:**
- Consumes: the `update_tiebreakers` command from Task 2.
- Produces: nothing for later tasks.

**Background for the implementer:**

`update_all.PIPELINE` is an ordered list of command names run in dependency order, and the module docstring above it repeats the same order as a numbered list — both must change together, and the numbering after the insertion point shifts by one. The new step belongs immediately after `update_games` (which supplies the kickoff times it reads) and before `update_missed_picks`.

`QUEUEABLE_COMMANDS` in `pickem_superadmin/jobs.py` gates which commands `/superadmin/jobs/` will queue; `run_command` raises `ValueError` for anything not listed.

- [ ] **Step 1: Write the failing tests**

Append to `pickem/pickem_api/tests/test_update_tiebreakers.py`:

```python
class PipelineWiringTests(TestCase):
    def test_runs_after_update_games_and_before_missed_picks(self):
        from pickem_api.management.commands.update_all import PIPELINE

        self.assertIn("update_tiebreakers", PIPELINE)
        self.assertEqual(
            PIPELINE.index("update_tiebreakers"),
            PIPELINE.index("update_games") + 1,
        )
        self.assertLess(
            PIPELINE.index("update_tiebreakers"),
            PIPELINE.index("update_missed_picks"),
        )

    def test_is_queueable_from_superadmin(self):
        from pickem_superadmin.jobs import QUEUEABLE_COMMANDS

        self.assertIn("update_tiebreakers", QUEUEABLE_COMMANDS)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run python manage.py test pickem_api.tests.test_update_tiebreakers.PipelineWiringTests --settings=pickem.test_settings
```
Expected: FAIL, both tests — `'update_tiebreakers' not found in [...]`.

- [ ] **Step 3: Insert the pipeline step**

In `pickem/pickem_api/management/commands/update_all.py`, change `PIPELINE` to:

```python
PIPELINE = [
    "update_records",
    "update_games",
    "update_tiebreakers",
    "update_missed_picks",
    "update_picks",
    "update_standings",
    "update_weekly_winners",
    "update_rankings",
    "update_season_winners",
    "generate_weekly_summaries",
    "update_stats",
]
```

And update the module docstring's ordered list to match, renumbering everything
after the insertion:

```
Order matters:
  1. update_records          - team win/loss records (independent)
  2. update_games            - fetch scores + winners from ESPN
  3. update_tiebreakers      - flag each week's last game as the tiebreaker
  4. update_missed_picks     - apply missed-pick policies before grading
  5. update_picks            - score picks against game winners
  6. update_standings        - recompute per-pool weekly/total points
  7. update_weekly_winners   - award winner bonuses once the week completes
  8. update_rankings         - rank pool members by total points (incl. bonus)
  9. update_season_winners   - flag the season champion once the season ends
  10. generate_weekly_summaries - AI recap drafts (after winners are final,
     so a week-18 recap can reference the just-crowned champion)
  11. update_stats           - recompute per-user userStats (replaces pickemctl)
```

- [ ] **Step 4: Add to the superadmin allowlist**

In `pickem/pickem_superadmin/jobs.py`, add `'update_tiebreakers'` to
`QUEUEABLE_COMMANDS`, after `'update_games'` to mirror pipeline order:

```python
QUEUEABLE_COMMANDS = (
    'update_all',
    'update_games',
    'update_tiebreakers',
    'update_picks',
    'update_standings',
    'update_stats',
    'update_records',
    'update_weekly_winners',
    'update_season_winners',
    'update_missed_picks',
    'update_rankings',
    'prune_superadmin_logs',
)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```bash
uv run python manage.py test pickem_api.tests.test_update_tiebreakers --settings=pickem.test_settings
```
Expected: PASS, 15 tests.

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_api/management/commands/update_all.py \
        pickem/pickem_superadmin/jobs.py \
        pickem/pickem_api/tests/test_update_tiebreakers.py
git commit -m "$(cat <<'EOF'
feat(pipeline): run update_tiebreakers after update_games

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EKQvoUBZ6qDWj5YsRS8nY7
EOF
)"
```

---

### Task 4: Document the new step and verify the whole suite

**Files:**
- Modify: `CLAUDE.md` — the numbered list under "Data Pipeline & Automated Updates"

**Interfaces:**
- Consumes: everything above.
- Produces: nothing.

- [ ] **Step 1: Update the pipeline list in CLAUDE.md**

Insert the new step and renumber those after it:

```
1. `update_records` - team win/loss records (independent)
2. `update_games` - fetch scores + winners from ESPN
3. `update_tiebreakers` - flag each week's last game as the tiebreaker (skips a
   week whose games all share one placeholder kickoff, e.g. week 18 before the
   schedule is published)
4. `update_missed_picks` - apply missed-pick policies before grading
5. `update_picks` - score picks against game winners
6. `update_standings` - recompute per-pool weekly/total points
7. `update_weekly_winners` - award winner bonuses once the week completes
8. `update_rankings` - rank pool members by total points (incl. bonus)
9. `update_season_winners` - flag the season champion once the season ends
10. `generate_weekly_summaries` - AI recap drafts
11. `update_stats` - recompute per-user `userStats`
```

- [ ] **Step 2: Run the full test suite**

Run:
```bash
uv run python manage.py test --settings=pickem.test_settings
```
Expected: PASS. Known artifact from prior sessions: a "3 failures + 2 errors"
result when running against local postgres **with `--keepdb`** comes from stale
test-DB state, not a regression — the command above omits `--keepdb`, so
anything failing here is real and yours to fix.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: note update_tiebreakers in the pipeline order

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EKQvoUBZ6qDWj5YsRS8nY7
EOF
)"
```

---

## After the plan: the one-time backfill

**Not** a task for the implementing agent — this runs against production data
after the change ships.

```bash
python manage.py update_tiebreakers --season <YYZZ> --all-weeks --dry-run
python manage.py update_tiebreakers --season <YYZZ> --all-weeks
```

Or queue `update_tiebreakers` from `/superadmin/jobs/` once deployed (that path
covers the current week only). Any week whose games all share a placeholder
kickoff reports "skipped, no single last game" and is picked up automatically on
a later run once ESPN publishes its times.
