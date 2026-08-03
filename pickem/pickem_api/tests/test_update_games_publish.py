from unittest import mock

from django.test import TestCase

from pickem_api.management.commands import update_games as ug

# All 10 per-quarter period fields, zeroed — included so an "unchanged" game
# compares equal across SCORE_TRIGGER_FIELDS (which now includes the periods).
PERIODS = {
    "homeTeamPeriod1": 0, "homeTeamPeriod2": 0, "homeTeamPeriod3": 0,
    "homeTeamPeriod4": 0, "homeTeamPeriodOT": 0,
    "awayTeamPeriod1": 0, "awayTeamPeriod2": 0, "awayTeamPeriod3": 0,
    "awayTeamPeriod4": 0, "awayTeamPeriodOT": 0,
}


class PublishChangedGameTests(TestCase):
    def _game(self, **kw):
        base = dict(
            id=401, gameseason=2627, gameWeek="3",
            homeTeamScore=0, awayTeamScore=0, statusType="notstarted",
            statusTitle="", gameWinner="",
            **PERIODS,
        )
        base.update(kw)
        return mock.Mock(**base)

    def test_publishes_when_live_field_changed(self):
        before = {"homeTeamScore": 0, "awayTeamScore": 0, "statusType": "notstarted",
                  "statusTitle": "", "gameWinner": "", **PERIODS}
        after = self._game(homeTeamScore=7, statusType="inprogress")
        with mock.patch.object(ug, "publish_score_event") as pub:
            ug.maybe_publish_game_change(before, after)
            self.assertEqual(pub.call_count, 1)
            args = pub.call_args.args
            self.assertEqual(args[0], 2627)      # season
            self.assertEqual(args[1], "3")       # week
            self.assertEqual(args[2]["home_score"], 7)

    def test_publishes_when_only_status_title_changed(self):
        # Clock tick: statusType unchanged (inprogress), only statusTitle changes.
        before = {"homeTeamScore": 7, "awayTeamScore": 0, "statusType": "inprogress",
                  "statusTitle": "5:00 - 2nd Quarter", "gameWinner": "", **PERIODS}
        after = self._game(homeTeamScore=7, awayTeamScore=0, statusType="inprogress",
                           statusTitle="4:45 - 2nd Quarter", gameWinner="")
        with mock.patch.object(ug, "publish_score_event") as pub:
            ug.maybe_publish_game_change(before, after)
            self.assertEqual(pub.call_count, 1)

    def test_no_publish_when_unchanged(self):
        before = {"homeTeamScore": 7, "awayTeamScore": 0, "statusType": "inprogress",
                  "statusTitle": "Q1", "gameWinner": "", **PERIODS}
        after = self._game(homeTeamScore=7, awayTeamScore=0, statusType="inprogress",
                           statusTitle="Q1", gameWinner="")
        with mock.patch.object(ug, "publish_score_event") as pub:
            ug.maybe_publish_game_change(before, after)
            pub.assert_not_called()

    def test_publishes_new_game(self):
        after = self._game(statusType="notstarted")
        with mock.patch.object(ug, "publish_score_event") as pub:
            ug.maybe_publish_game_change(None, after)  # None = newly created
            self.assertEqual(pub.call_count, 1)
