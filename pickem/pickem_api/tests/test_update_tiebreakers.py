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
