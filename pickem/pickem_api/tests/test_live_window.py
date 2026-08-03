from unittest import mock

from django.test import TestCase

from pickem_api import scheduler
from pickem_api.models import GamesAndScores


class LiveWindowTests(TestCase):
    def test_inactive_when_no_inprogress_games(self):
        self.assertFalse(scheduler.live_window_active())

    def test_active_with_an_inprogress_game(self):
        # No currentSeason row exists in this test, so get_season() falls back
        # to its default (2024) — match that here rather than the "real"
        # 2627 season used elsewhere.
        GamesAndScores.objects.create(
            id=1, slug="a-at-h", competition="1", gameWeek="3", gameyear="2024",
            gameseason=2024, startTimestamp="2024-09-21T17:00:00Z",
            statusType="inprogress", statusTitle="In Progress",
            homeTeamId=1, homeTeamSlug="home", homeTeamName="Home",
            awayTeamId=2, awayTeamSlug="away", awayTeamName="Away",
        )
        self.assertTrue(scheduler.live_window_active())

    def test_tick_runs_update_games_only_when_active(self):
        with mock.patch.object(scheduler, "live_window_active", return_value=False), \
                mock.patch.object(scheduler, "run_job_once") as run:
            scheduler.run_live_scores_tick()
            run.assert_not_called()
        with mock.patch.object(scheduler, "live_window_active", return_value=True), \
                mock.patch.object(scheduler, "run_job_once") as run:
            scheduler.run_live_scores_tick()
            run.assert_called_once_with("update_games")
