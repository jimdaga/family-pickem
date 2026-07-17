"""Pipeline runner and assertions for the grading integration suite.

Tests enter the grading engine through the same door production does: the
management commands, in ``update_all`` order. The only substitution is the
ESPN game-stats provider used by the combined-yards tiebreaker — the engine
takes an injectable provider precisely so tests never touch the network.
"""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from pickem_api.models import userSeasonPoints

from .factories import SEASON

#: The grading slice of the production ``update_all`` pipeline. The two ESPN
#: fetch steps (update_records, update_games) are replaced by synthetic data;
#: update_season_winners/update_stats are downstream of standings and out of
#: scope for this suite.
PIPELINE = [
    "update_missed_picks",
    "update_picks",
    "update_standings",
    "update_weekly_winners",
    "update_rankings",
]


class StubStatsProvider:
    """GameStatsProvider stand-in for the combined-yards tiebreaker.

    Configure a flat ``yards`` value or a ``per_game`` mapping of game id to
    yards. Unconfigured lookups raise, which the engine treats exactly like
    an ESPN outage (award deferred) — tests exercising that path get it for
    free, and tests that hit it by accident fail visibly on standings.
    """

    def __init__(self, yards=None, per_game=None):
        self.yards = yards
        self.per_game = per_game or {}
        self.calls = 0

    def combined_yards(self, game_id):
        self.calls += 1
        if game_id in self.per_game:
            return self.per_game[game_id]
        if self.yards is None:
            raise LookupError(f"StubStatsProvider has no yards for game {game_id}")
        return self.yards


class GradingTestCase(TestCase):
    """Base class: run the real pipeline, assert exact standings."""

    def run_pipeline(self, *, season=SEASON, yards=None, per_game_yards=None, week=None):
        """Run the grading pipeline once, as the scheduler would.

        Production runs ``update_all`` every minute; a week's winner is
        awarded on the first run after its last game goes final. Multi-week
        tests should therefore finish a week's games, call this, and repeat —
        ``update_weekly_winners`` only awards the *latest* complete week.

        Returns the combined command output (handy for asserting messages).
        """
        stub = StubStatsProvider(yards=yards, per_game=per_game_yards)
        out = StringIO()
        with mock.patch(
            "pickem_api.management.commands.update_weekly_winners.EspnGameStatsProvider",
            return_value=stub,
        ):
            for command in PIPELINE:
                kwargs = {"season": season}
                if command == "update_weekly_winners" and week is not None:
                    kwargs["week"] = week
                call_command(command, stdout=out, stderr=out, **kwargs)
        self.last_stats_stub = stub
        return out.getvalue()

    # ------------------------------------------------------------------
    # Assertions — always exact and exhaustive for the pool they target.
    # ------------------------------------------------------------------

    def standings_row(self, pool, user, *, season=SEASON):
        return userSeasonPoints.objects.get(
            pool=pool, gameseason=season, userID=str(user.id)
        )

    def assertStandings(self, pool, expected, *, season=SEASON):
        """``expected``: iterable of (user, total_points, current_rank).

        Exhaustive on purpose: every row in the pool's standings must be
        accounted for, so a user leaking in from another pool fails the test
        even when the expected users' numbers are all correct.
        """
        rows = userSeasonPoints.objects.filter(pool=pool, gameseason=season)
        actual = {
            row.userID: (row.total_points, row.current_rank) for row in rows
        }
        wanted = {
            str(user.id): (total, rank) for user, total, rank in expected
        }
        names = {str(user.id): user.username for user, _, _ in expected}
        readable_actual = {
            names.get(uid, f"<unexpected userID {uid}>"): vals
            for uid, vals in sorted(actual.items())
        }
        readable_wanted = {
            names[uid]: vals for uid, vals in sorted(wanted.items())
        }
        self.assertEqual(
            readable_actual,
            readable_wanted,
            f"Standings mismatch for {pool} (season {season}): "
            "values are (total_points, current_rank)",
        )

    def assertWeek(self, pool, user, week, *, points=None, bonus=None,
                   winner=None, season=SEASON):
        """Check a user's per-week ledger; only the supplied fields."""
        row = self.standings_row(pool, user, season=season)
        label = f"{user.username} week {week} in {pool}"
        if points is not None:
            self.assertEqual(
                getattr(row, f"week_{week}_points"), points, f"{label}: points"
            )
        if bonus is not None:
            self.assertEqual(
                getattr(row, f"week_{week}_bonus"), bonus, f"{label}: bonus"
            )
        if winner is not None:
            self.assertEqual(
                getattr(row, f"week_{week}_winner"), winner, f"{label}: winner flag"
            )
