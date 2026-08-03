from unittest import mock

from django.test import TestCase

from pickem_api import scheduler
from pickem_api.models import GamesAndScores, ScheduledJobConfig


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

    def test_tick_skips_update_games_when_already_running(self):
        # Even during a live window, the live-scores tick must not kick off a
        # second update_games run if the pipeline tick (or a prior live tick)
        # already has one in flight — guards against overlapping runs since
        # max_instances=1 is only scoped per-APScheduler-job.
        with mock.patch.object(scheduler, "live_window_active", return_value=True), \
                mock.patch.object(scheduler, "_update_games_running", return_value=True), \
                mock.patch.object(scheduler, "run_job_once") as run:
            scheduler.run_live_scores_tick()
            run.assert_not_called()

    def test_no_finished_unscored_when_no_games(self):
        self.assertFalse(scheduler.finished_unscored_exists())

    def test_finished_unscored_exists_true_for_finished_unscored_game(self):
        # No currentSeason row exists in this test, so get_season() falls back
        # to its default (2024) — match that here rather than the "real"
        # 2627 season used elsewhere.
        GamesAndScores.objects.create(
            id=1, slug="a-at-h", competition="1", gameWeek="3", gameyear="2024",
            gameseason=2024, startTimestamp="2024-09-21T17:00:00Z",
            statusType="finished", statusTitle="Final",
            homeTeamId=1, homeTeamSlug="home", homeTeamName="Home",
            awayTeamId=2, awayTeamSlug="away", awayTeamName="Away",
            gameScored=False,
        )
        self.assertTrue(scheduler.finished_unscored_exists())

    def test_finished_unscored_exists_false_when_already_scored(self):
        GamesAndScores.objects.create(
            id=1, slug="a-at-h", competition="1", gameWeek="3", gameyear="2024",
            gameseason=2024, startTimestamp="2024-09-21T17:00:00Z",
            statusType="finished", statusTitle="Final",
            homeTeamId=1, homeTeamSlug="home", homeTeamName="Home",
            awayTeamId=2, awayTeamSlug="away", awayTeamName="Away",
            gameScored=True,
        )
        self.assertFalse(scheduler.finished_unscored_exists())

    def test_tick_runs_downstream_chain_when_finished_unscored_exists(self):
        with mock.patch.object(scheduler, "live_window_active", return_value=True), \
                mock.patch.object(scheduler, "_update_games_running", return_value=False), \
                mock.patch.object(scheduler, "finished_unscored_exists", return_value=True), \
                mock.patch.object(scheduler, "run_job_once") as run:
            scheduler.run_live_scores_tick()
            self.assertEqual(
                run.call_args_list,
                [
                    mock.call("update_games"),
                    mock.call("update_picks"),
                    mock.call("update_standings"),
                    mock.call("update_rankings"),
                    mock.call("update_stats"),
                ],
            )

    def test_tick_skips_downstream_chain_when_no_finished_unscored(self):
        with mock.patch.object(scheduler, "live_window_active", return_value=True), \
                mock.patch.object(scheduler, "_update_games_running", return_value=False), \
                mock.patch.object(scheduler, "finished_unscored_exists", return_value=False), \
                mock.patch.object(scheduler, "run_job_once") as run:
            scheduler.run_live_scores_tick()
            run.assert_called_once_with("update_games")

    def test_job_enabled_defaults_true_when_no_config_row(self):
        self.assertTrue(scheduler._job_enabled("update_stats"))

    def test_job_enabled_respects_disabled_config_row(self):
        ScheduledJobConfig.objects.create(job_id="update_stats", enabled=False)
        self.assertFalse(scheduler._job_enabled("update_stats"))
        ScheduledJobConfig.objects.create(job_id="update_picks", enabled=True)
        self.assertTrue(scheduler._job_enabled("update_picks"))

    def test_tick_skips_update_games_when_disabled(self):
        # Disabling update_games in the superadmin console must not be
        # silently overridden by the fast live tick.
        ScheduledJobConfig.objects.create(job_id="update_games", enabled=False)
        with mock.patch.object(scheduler, "live_window_active", return_value=True), \
                mock.patch.object(scheduler, "_update_games_running", return_value=False), \
                mock.patch.object(scheduler, "finished_unscored_exists", return_value=True), \
                mock.patch.object(scheduler, "run_job_once") as run:
            scheduler.run_live_scores_tick()
            self.assertEqual(
                run.call_args_list,
                [
                    mock.call("update_picks"),
                    mock.call("update_standings"),
                    mock.call("update_rankings"),
                    mock.call("update_stats"),
                ],
            )

    def test_tick_skips_disabled_downstream_job(self):
        # A disabled downstream step (e.g. update_stats disabled via the
        # superadmin console) must be skipped, matching pipeline behavior.
        ScheduledJobConfig.objects.create(job_id="update_stats", enabled=False)
        with mock.patch.object(scheduler, "live_window_active", return_value=True), \
                mock.patch.object(scheduler, "_update_games_running", return_value=False), \
                mock.patch.object(scheduler, "finished_unscored_exists", return_value=True), \
                mock.patch.object(scheduler, "run_job_once") as run:
            scheduler.run_live_scores_tick()
            self.assertEqual(
                run.call_args_list,
                [
                    mock.call("update_games"),
                    mock.call("update_picks"),
                    mock.call("update_standings"),
                    mock.call("update_rankings"),
                ],
            )
