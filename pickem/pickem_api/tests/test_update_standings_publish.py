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


class CurrentWeekSeasonScopingTests(TestCase):
    """_current_week() must be scoped to its season so a same-date GameWeeks
    row from another season (notably the dev-only demo season 9999) can't leak
    the wrong week into a real season's live-standings payload."""

    def _week_row(self, season, week):
        from django.utils import timezone
        from pickem_api.models import GameWeeks
        return GameWeeks.objects.create(
            date=timezone.localdate(), competition="nfl", season=season,
            weekNumber=week,
        )

    def test_real_season_ignores_demo_season_row_for_today(self):
        # A real season's row and the demo row share today's date.
        self._week_row(season=2627, week=7)
        self._week_row(season=9999, week=1)  # demo
        self.assertEqual(us.Command._current_week(2627), 7)
        self.assertEqual(us.Command._current_week(9999), 1)

    def test_demo_row_alone_does_not_leak_into_real_season(self):
        # Only the demo row exists for today; a real season must NOT pick it up.
        self._week_row(season=9999, week=1)
        self.assertIsNone(us.Command._current_week(2627))
        self.assertEqual(us.Command._current_week(9999), 1)

    def test_falls_back_to_legacy_null_season_row(self):
        # Historical rows predate the season column (season=NULL); a season
        # lookup still resolves them via the fallback.
        self._week_row(season=None, week=5)
        self.assertEqual(us.Command._current_week(2627), 5)

    def test_no_row_returns_none(self):
        self.assertIsNone(us.Command._current_week(2627))
