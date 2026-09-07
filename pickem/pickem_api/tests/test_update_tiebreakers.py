from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from grading_tests.factories import create_game
from pickem_api.management.commands import update_tiebreakers as ut
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

    def test_whole_week_tied_leaves_week_untouched(self):
        # ESPN's unpublished-schedule state: every game shares one placeholder
        # kickoff, so there is no identifiable last game.
        a = self._game(18, 5)
        b = self._game(18, 5, flagged=True)
        c = self._game(18, 5)

        self.assertIsNone(set_week_tiebreaker(SEASON, 18, "nfl"))

        for game in (a, b, c):
            game.refresh_from_db()
        self.assertFalse(a.tieBreakerGame)
        self.assertFalse(c.tieBreakerGame)
        # The pre-existing flag survives: a week we cannot reason about is a
        # week we do not touch.
        self.assertTrue(b.tieBreakerGame)

    def test_doubleheader_takes_lowest_game_id(self):
        # Two games genuinely share the last slot (a Monday-night doubleheader).
        # The week has a real last kickoff, so it must still get a tiebreaker.
        self._game(14, 0)
        first = self._game(14, 30)
        second = self._game(14, 30)
        lower, higher = sorted([first, second], key=lambda g: g.id)

        self.assertEqual(set_week_tiebreaker(SEASON, 14, "nfl"), lower.id)
        self.assertEqual(self._flagged_ids(14), {lower.id})
        higher.refresh_from_db()
        self.assertFalse(higher.tieBreakerGame)

    def test_doubleheader_clears_flag_from_the_other_tied_game(self):
        self._game(15, 0)
        first = self._game(15, 30)
        second = self._game(15, 30)
        lower, higher = sorted([first, second], key=lambda g: g.id)
        GamesAndScores.objects.filter(id=higher.id).update(tieBreakerGame=True)

        self.assertEqual(set_week_tiebreaker(SEASON, 15, "nfl"), lower.id)
        self.assertEqual(self._flagged_ids(15), {lower.id})

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
