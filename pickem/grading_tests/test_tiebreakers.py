"""Scenarios 2–3 — the default tiebreaker chain.

Default pool rules: primary = closest predicted total score of the
tiebreaker (MNF) game, secondary = closest predicted combined offensive
yards. Distance is absolute, so equidistant predictions (40 and 50 around
an actual 45) tie the primary and fall through to the secondary.

Combined yards come from ESPN in production; here the injected stub plays
ESPN, so the real engine code runs end-to-end without network.
"""

from .factories import create_game, create_league, finish_game, make_pick
from .harness import GradingTestCase


class TiebreakerChainTest(GradingTestCase):

    def setUp(self):
        """alice and bob finish the week on identical pick totals (2 each),
        so the weekly winner always comes down to the tiebreaker chain."""
        self.league = create_league("alice", "bob")
        self.pool = self.league.pool
        self.opener = create_game(1)
        self.mnf = create_game(1, mnf=True)

    def _run_week(self, *, alice, bob, yards=None):
        """Both users pick both winners; tiebreaker predictions differ."""
        for user, (score, predicted_yards) in (
            (self.league["alice"], alice),
            (self.league["bob"], bob),
        ):
            make_pick(self.pool, user, self.opener, "home")
            make_pick(
                self.pool, user, self.mnf, "home",
                score=score, yards=predicted_yards,
            )
        finish_game(self.opener, 20, 13)
        finish_game(self.mnf, 24, 21)  # actual combined score: 45
        return self.run_pipeline(yards=yards)

    def test_first_tiebreaker_closest_total_score_wins(self):
        self._run_week(
            alice=(44, None),  # off by 1
            bob=(48, None),    # off by 3
        )

        self.assertWeek(self.pool, self.league["alice"], 1, bonus=2, winner=True)
        self.assertWeek(self.pool, self.league["bob"], 1, winner=False)
        self.assertStandings(self.pool, [
            (self.league["alice"], 4, 1),
            (self.league["bob"], 2, 2),
        ])

    def test_equidistant_predictions_fall_through_to_combined_yards(self):
        # The spec's exact case: actual total 45, predictions 40 and 50 are
        # equally close — the primary tiebreaker is itself a tie, and the
        # secondary (combined yards) must decide.
        self._run_week(
            alice=(40, 690),   # score off 5; yards off 10 of actual 700
            bob=(50, 800),     # score off 5; yards off 100
            yards=700,
        )

        # The engine really consulted the (stubbed) stats provider.
        self.assertGreaterEqual(self.last_stats_stub.calls, 1)
        self.assertWeek(self.pool, self.league["alice"], 1, bonus=2, winner=True)
        self.assertWeek(self.pool, self.league["bob"], 1, winner=False)
        self.assertStandings(self.pool, [
            (self.league["alice"], 4, 1),
            (self.league["bob"], 2, 2),
        ])

    def test_second_tiebreaker_selects_correct_winner_outright(self):
        # Primary dead heat again, but this time bob's yards are closer.
        self._run_week(
            alice=(40, 500),   # yards off 200
            bob=(50, 720),     # yards off 20
            yards=700,
        )

        self.assertWeek(self.pool, self.league["bob"], 1, bonus=2, winner=True)
        self.assertStandings(self.pool, [
            (self.league["bob"], 4, 1),
            (self.league["alice"], 2, 2),
        ])

    def test_chain_exhausted_means_co_winners_with_full_bonus(self):
        # Equidistant scores AND equidistant yards: nothing can separate
        # them, so both are weekly winners and each gets the full bonus.
        self._run_week(
            alice=(40, 690),
            bob=(50, 710),
            yards=700,
        )

        self.assertWeek(self.pool, self.league["alice"], 1, bonus=2, winner=True)
        self.assertWeek(self.pool, self.league["bob"], 1, bonus=2, winner=True)
        self.assertStandings(self.pool, [
            (self.league["alice"], 4, 1),
            (self.league["bob"], 4, 1),
        ])

    def test_missing_yards_data_defers_award_instead_of_guessing(self):
        # ESPN outage: the provider errors. Points must still land, but the
        # bonus is deferred (not guessed, not co-awarded) until data exists.
        with self.assertLogs("pickem_api.weekly_winners", level="ERROR"):
            self._run_week(
                alice=(40, 690),
                bob=(50, 800),
                yards=None,  # stub raises, exactly like an ESPN failure
            )

        self.assertWeek(self.pool, self.league["alice"], 1, points=2, winner=False)
        self.assertWeek(self.pool, self.league["bob"], 1, points=2, winner=False)

        # The next scheduler run finds ESPN healthy and awards normally.
        self.run_pipeline(yards=700)
        self.assertWeek(self.pool, self.league["alice"], 1, bonus=2, winner=True)
        self.assertWeek(self.pool, self.league["bob"], 1, winner=False)
