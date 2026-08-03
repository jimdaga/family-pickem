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
