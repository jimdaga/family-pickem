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
            us.maybe_publish_standings_change(10, 6, row, 3, 2627)
            self.assertEqual(pub.call_count, 1)
            channel, payload = pub.call_args.args
            self.assertEqual(channel, "standings:7:2627")
            self.assertEqual(payload["total_points"], 13)
            self.assertEqual(payload["week"], 3)

    def test_publishes_when_newly_created(self):
        row = self._row(total_points=0)
        with mock.patch.object(us, "publish_event") as pub:
            us.maybe_publish_standings_change(None, None, row, 3, 2627)
            self.assertEqual(pub.call_count, 1)

    def test_no_publish_when_unchanged(self):
        row = self._row(total_points=10)
        with mock.patch.object(us, "publish_event") as pub:
            us.maybe_publish_standings_change(10, 6, row, 3, 2627)
            pub.assert_not_called()

    def test_publishes_when_week_points_changed_but_total_unchanged(self):
        # A cross-week scoring correction can change week_N_points while
        # total_points stays the same (e.g. an offsetting adjustment in
        # another week). The lobby shows week_N_points, so this must still
        # publish.
        row = self._row(total_points=10, week_3_points=9)
        with mock.patch.object(us, "publish_event") as pub:
            us.maybe_publish_standings_change(10, 6, row, 3, 2627)
            self.assertEqual(pub.call_count, 1)
            channel, payload = pub.call_args.args
            self.assertEqual(channel, "standings:7:2627")
            self.assertEqual(payload["week"], 3)
