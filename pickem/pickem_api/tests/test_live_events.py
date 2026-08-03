from unittest import mock

from django.test import SimpleTestCase

from pickem_api import live_events


class ChannelAndPayloadTests(SimpleTestCase):
    def test_channel_name(self):
        self.assertEqual(live_events.scores_channel(2627, "3"), "scores:2627:3")

    def test_payload_has_compact_live_fields(self):
        game = mock.Mock(
            id=401, homeTeamScore=14, awayTeamScore=7, statusType="inprogress",
            statusTitle="Q2 5:00", gameWinner="",
        )
        payload = live_events.score_event_payload(game)
        self.assertEqual(payload["game_id"], 401)
        self.assertEqual(payload["home_score"], 14)
        self.assertEqual(payload["away_score"], 7)
        self.assertEqual(payload["status"], "inprogress")
        self.assertEqual(payload["winner"], "")


class PublishTests(SimpleTestCase):
    def test_publish_no_redis_url_is_noop(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            # Must not raise even with no REDIS_URL configured.
            live_events.publish_score_event(2627, "3", {"game_id": 1})

    def test_publish_swallows_redis_errors(self):
        boom = mock.Mock(side_effect=RuntimeError("down"))
        with mock.patch.dict("os.environ", {"REDIS_URL": "redis://x:6379/1"}), \
                mock.patch.object(live_events, "_redis_client", return_value=mock.Mock(publish=boom)):
            # Best-effort: a Redis error must be swallowed (logged), not raised.
            live_events.publish_score_event(2627, "3", {"game_id": 1})


class StandingsEventTests(SimpleTestCase):
    def test_standings_channel(self):
        self.assertEqual(live_events.standings_channel(7, 2627), "standings:7:2627")

    def test_standings_payload(self):
        from unittest import mock
        row = mock.Mock(userID="u1", total_points=42, current_rank=2)
        setattr(row, "week_3_points", 5)
        p = live_events.standings_event_payload(row, 3)
        self.assertEqual(p["user_id"], "u1")
        self.assertEqual(p["total_points"], 42)
        self.assertEqual(p["week"], 3)
        self.assertEqual(p["week_points"], 5)


class ScorePayloadPeriodsTests(SimpleTestCase):
    def test_score_payload_includes_periods_and_status_title(self):
        from unittest import mock
        g = mock.Mock(id=1, homeTeamScore=7, awayTeamScore=0, statusType="inprogress",
                      statusTitle="5:00 - 2nd Quarter", gameWinner="",
                      homeTeamPeriod1=7, homeTeamPeriod2=0, homeTeamPeriod3=0,
                      homeTeamPeriod4=0, homeTeamPeriodOT=0,
                      awayTeamPeriod1=0, awayTeamPeriod2=0, awayTeamPeriod3=0,
                      awayTeamPeriod4=0, awayTeamPeriodOT=0)
        p = live_events.score_event_payload(g)
        self.assertEqual(p["status_title"], "5:00 - 2nd Quarter")
        self.assertEqual(p["home_periods"], [7, 0, 0, 0, 0])
        self.assertEqual(p["away_periods"], [0, 0, 0, 0, 0])
