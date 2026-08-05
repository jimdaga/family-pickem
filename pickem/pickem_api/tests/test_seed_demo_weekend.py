from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from io import StringIO

from pickem_api import demo_weekend as dw
from pickem_api.models import (
    Family, GamePicks, GamesAndScores, Pool, currentSeason,
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

    def test_wipe_removes_everything(self):
        call_command("seed_demo_weekend", stdout=StringIO())
        call_command("seed_demo_weekend", "--wipe", stdout=StringIO())
        self.assertFalse(Family.objects.filter(slug=dw.DEMO_SLUG).exists())
        self.assertEqual(
            GamesAndScores.objects.filter(gameseason=dw.DEMO_SEASON).count(), 0)

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
