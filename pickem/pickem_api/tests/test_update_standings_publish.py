from unittest import mock

from django.test import TestCase

from pickem_api.management.commands import update_standings as us


class MaybePublishStandingsChangeTests(TestCase):
    def _row(self, **kw):
        base = dict(pool_id=7, userID="42", total_points=10, week_3_points=6,
                    current_rank=2)
        base.update(kw)
        return mock.Mock(**base)

    def test_publishes_when_total_changed(self):
        row = self._row(total_points=13)
        with mock.patch.object(us, "publish_event") as pub:
            us.maybe_publish_standings_change(10, row, 3, 2627)
            self.assertEqual(pub.call_count, 1)
            channel, payload = pub.call_args.args
            self.assertEqual(channel, "standings:7:2627")
            self.assertEqual(payload["total_points"], 13)
            self.assertEqual(payload["week"], 3)

    def test_publishes_when_newly_created(self):
        row = self._row(total_points=0)
        with mock.patch.object(us, "publish_event") as pub:
            us.maybe_publish_standings_change(None, row, 3, 2627)
            self.assertEqual(pub.call_count, 1)

    def test_no_publish_when_unchanged(self):
        row = self._row(total_points=10)
        with mock.patch.object(us, "publish_event") as pub:
            us.maybe_publish_standings_change(10, row, 3, 2627)
            pub.assert_not_called()
