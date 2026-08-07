from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from io import StringIO

from django.utils import timezone

from pickem_api import demo_weekend as dw
from pickem_api.models import (
    Family, GamePicks, GamesAndScores, GameWeeks, Pool, currentSeason,
)


@override_settings(DEBUG=True)
class SeedDemoWeekendTests(TestCase):
    def test_seeds_expected_shape_pre_kickoff(self):
        call_command("seed_demo_weekend", stdout=StringIO())
        self.assertTrue(Family.objects.filter(slug=dw.DEMO_SLUG).exists())
        self.assertTrue(
            Pool.objects.filter(family__slug=dw.DEMO_SLUG,
                                slug=dw.DEMO_POOL_SLUG).exists())
        games = GamesAndScores.objects.filter(gameseason=dw.DEMO_SEASON)
        self.assertEqual(games.count(), len(dw.GAMES))
        # Every game seeded pre-kickoff: not started, scoreless, ungraded.
        for g in games:
            self.assertEqual(g.statusType, "notstarted")
            self.assertEqual(g.homeTeamScore, 0)
            self.assertFalse(g.gameScored)
        expected_picks = sum(len(cfg["picks"]) for cfg in dw.PICKS.values())
        self.assertEqual(
            GamePicks.objects.filter(gameseason=dw.DEMO_SEASON).count(),
            expected_picks)

    def test_seeds_gameweek_for_today_so_live_week_resolves(self):
        # update_standings._current_week() looks up GameWeeks by today's date;
        # without a row it publishes week=null and the lobby drops the event.
        # The seeder adds a demo row for today so the live path works.
        call_command("seed_demo_weekend", stdout=StringIO())
        row = GameWeeks.objects.filter(
            date=timezone.localdate(), season=dw.DEMO_SEASON).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.weekNumber, int(dw.DEMO_WEEK))

    def test_seeds_gameweek_only_when_today_has_no_real_row(self):
        # Never shadow a real-season week row for today.
        GameWeeks.objects.create(
            date=timezone.localdate(), competition="nfl", season=2627,
            weekNumber=5)
        call_command("seed_demo_weekend", stdout=StringIO())
        self.assertFalse(
            GameWeeks.objects.filter(
                date=timezone.localdate(), season=dw.DEMO_SEASON).exists())
        # The real row is untouched.
        self.assertEqual(
            GameWeeks.objects.get(
                date=timezone.localdate(), season=2627).weekNumber, 5)

    def test_wipe_removes_everything(self):
        call_command("seed_demo_weekend", stdout=StringIO())
        call_command("seed_demo_weekend", "--wipe", stdout=StringIO())
        self.assertFalse(Family.objects.filter(slug=dw.DEMO_SLUG).exists())
        self.assertEqual(
            GamesAndScores.objects.filter(gameseason=dw.DEMO_SEASON).count(), 0)
        self.assertEqual(
            GameWeeks.objects.filter(season=dw.DEMO_SEASON).count(), 0)

    def test_make_current_and_print(self):
        currentSeason.objects.create(season=2627)
        call_command("seed_demo_weekend", "--make-current", stdout=StringIO())
        self.assertEqual(currentSeason.objects.first().season, dw.DEMO_SEASON)
        out = StringIO()
        call_command("seed_demo_weekend", "--print-current-season", stdout=out)
        self.assertEqual(out.getvalue().strip(), str(dw.DEMO_SEASON))

    def test_print_current_season_with_no_row_prints_bare_int(self):
        # No currentSeason row exists at all — get_season()'s own fallback
        # must still produce a bare integer for the orchestrator to parse.
        self.assertFalse(currentSeason.objects.exists())
        out = StringIO()
        call_command("seed_demo_weekend", "--print-current-season", stdout=out)
        printed = out.getvalue().strip()
        self.assertTrue(printed.isdigit(), f"expected a bare int, got {printed!r}")

    def test_refuses_without_debug(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                call_command("seed_demo_weekend", stdout=StringIO())
