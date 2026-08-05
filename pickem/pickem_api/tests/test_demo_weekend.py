from django.test import TestCase

from pickem_api import demo_weekend as dw


class DemoWeekendGeometryTests(TestCase):
    def test_slate_shape(self):
        self.assertEqual(dw.DEMO_SEASON, 9999)
        self.assertGreaterEqual(len(dw.GAMES), 13)
        self.assertGreaterEqual(len(dw.PLAYERS), 8)
        # Exactly one Monday-night tiebreaker game.
        self.assertEqual(sum(1 for g in dw.GAMES if g["tiebreaker"]), 1)

    def test_before_kickoff_is_scheduled_scoreless(self):
        g = dw.GAMES[0]
        st = dw.game_state_at(g, g["kickoff_frac"] - 0.001)
        self.assertEqual(st["statusType"], "notstarted")
        self.assertEqual(st["homeTeamScore"], 0)
        self.assertEqual(st["awayTeamScore"], 0)
        self.assertEqual(st["gameWinner"], "")

    def test_after_final_matches_line_totals(self):
        for g in dw.GAMES:
            st = dw.game_state_at(g, 1.0)
            self.assertEqual(st["statusType"], "finished")
            self.assertEqual(st["statusTitle"], "Final")
            self.assertEqual(st["homeTeamScore"], sum(g["home_line"]))
            self.assertEqual(st["awayTeamScore"], sum(g["away_line"]))
            self.assertEqual(st["gameWinner"], dw.game_winner(g))

    def test_live_scores_are_monotonic_nondecreasing(self):
        g = dw.GAMES[0]
        prev_h = prev_a = 0
        f = g["kickoff_frac"]
        while f <= g["final_frac"]:
            st = dw.game_state_at(g, f)
            self.assertGreaterEqual(st["homeTeamScore"], prev_h)
            self.assertGreaterEqual(st["awayTeamScore"], prev_a)
            prev_h, prev_a = st["homeTeamScore"], st["awayTeamScore"]
            f += 0.01

    def test_every_pick_targets_a_real_game_and_team(self):
        ids = {g["id"] for g in dw.GAMES}
        slugs = {g["home"] for g in dw.GAMES} | {g["away"] for g in dw.GAMES}
        for player, cfg in dw.PICKS.items():
            for gid, pick in cfg["picks"].items():
                self.assertIn(gid, ids)
                self.assertIn(pick, slugs)
