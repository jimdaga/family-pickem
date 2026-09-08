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
        # tiebreaker_game=False on purpose: mnf=True only places the later
        # kickoff. The flag itself must come from update_tiebreakers running in
        # the pipeline, so these scenarios exercise the real producer.
        self.mnf = create_game(1, mnf=True, tiebreaker_game=False)

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


class FlagMovedAfterPicksTest(GradingTestCase):
    """Characterization: what happens when the tiebreaker game moves after
    predictions are already in.

    There is deliberately NO kickoff freeze -- update_tiebreakers re-asserts
    the last game of the week on every tick, so a late ESPN schedule change can
    move the flag after picks lock. This test does not argue for or against
    that; it pins the consequence so a future change cannot alter it silently.
    """

    def setUp(self):
        self.league = create_league("alice", "bob")
        self.pool = self.league.pool
        self.opener = create_game(1)
        self.original_mnf = create_game(1, mnf=True, tiebreaker_game=False)

    def test_predictions_stay_on_the_old_game_and_stop_counting(self):
        from datetime import timedelta

        from pickem_api.models import GamePicks, GamesAndScores
        from pickem_api.management.commands.update_tiebreakers import (
            set_week_tiebreaker,
        )
        from .factories import SEASON

        # Week as originally scheduled: original_mnf is last, so it is flagged
        # and it is where both users enter their tiebreaker predictions.
        self.assertEqual(
            set_week_tiebreaker(SEASON, 1, "nfl"), self.original_mnf.id
        )
        for user, score in ((self.league["alice"], 44), (self.league["bob"], 48)):
            make_pick(self.pool, user, self.opener, "home")
            make_pick(
                self.pool, user, self.original_mnf, "home", score=score, yards=700
            )

        # A later game is flexed in after the fact.
        flexed = create_game(
            1,
            kickoff=self.original_mnf.startTimestamp + timedelta(hours=3),
            tiebreaker_game=False,
        )
        make_pick(self.pool, self.league["alice"], flexed, "home")
        make_pick(self.pool, self.league["bob"], flexed, "home")

        self.assertEqual(set_week_tiebreaker(SEASON, 1, "nfl"), flexed.id)

        # The flag moved. The predictions did not.
        self.assertFalse(
            GamesAndScores.objects.get(id=self.original_mnf.id).tieBreakerGame
        )
        self.assertTrue(GamesAndScores.objects.get(id=flexed.id).tieBreakerGame)

        kept = GamePicks.objects.filter(
            pool=self.pool, pick_game_id=self.original_mnf.id
        ).values_list("tieBreakerScore", flat=True)
        self.assertEqual(sorted(kept), [44, 48])

        # ...but they now sit on a game nobody grades against: every
        # prediction for the newly flagged game is NULL, so the primary
        # tiebreaker has nothing to compare and the week falls through to the
        # pool's secondary. This is the accepted cost of having no freeze.
        on_flagged = GamePicks.objects.filter(
            pool=self.pool, pick_game_id=flexed.id
        ).values_list("tieBreakerScore", flat=True)
        self.assertEqual(list(on_flagged), [None, None])
