from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from pickem_api import demo_weekend as dw
from pickem_api.management.commands import simulate_weekend as sw
from pickem_api.models import GamesAndScores


@override_settings(DEBUG=True)
class SimulateWeekendScoreTests(TestCase):
    def setUp(self):
        call_command("seed_demo_weekend", stdout=StringIO())

    def test_refuses_non_demo_season(self):
        with self.assertRaises(CommandError):
            call_command("simulate_weekend", "--season", "2627",
                        stdout=StringIO())

    def test_duration_zero_finalizes_all_games_and_publishes(self):
        with mock.patch("time.sleep"), \
             mock.patch.object(sw, "maybe_publish_game_change") as pub:
            call_command("simulate_weekend", "--duration", "0", "--tick", "0",
                        stdout=StringIO())
        # Every game is now final with its scripted totals.
        for g in dw.GAMES:
            row = GamesAndScores.objects.get(id=g["id"])
            self.assertEqual(row.statusType, "finished")
            self.assertEqual(row.homeTeamScore, sum(g["home_line"]))
            self.assertEqual(row.gameWinner, dw.game_winner(g))
        # A score publish fired for each game that changed (all of them).
        self.assertGreaterEqual(pub.call_count, len(dw.GAMES))

    def test_full_run_grades_and_flips_to_expected_week_winner(self):
        from pickem_api.models import userSeasonPoints
        with mock.patch("time.sleep"):
            call_command("simulate_weekend", "--duration", "0", "--tick", "0",
                        stdout=StringIO())
        # The scripted tiebreaker resolves to EXPECTED_WEEK_WINNER. The winner
        # flag lives on userSeasonPoints for the demo week; find who has it.
        winners = userSeasonPoints.objects.filter(
            gameseason=dw.DEMO_SEASON, **{f"week_{dw.DEMO_WEEK}_winner": True})
        winner_ids = {int(w.userID) for w in winners}
        from django.contrib.auth.models import User
        expected = User.objects.get(username=dw.EXPECTED_WEEK_WINNER)
        self.assertIn(expected.id, winner_ids)
