"""Scenario 6 — per-family rule configuration.

Every knob a commissioner can turn on ``PoolSettings`` that changes grading:
point weights, the weekly-winner bonus, each tiebreaker chain variant, and
the missed-pick policies. Adding a future rule = add a settings override in
``create_league(...)`` and assert the standings it should produce.
"""

from pickem_api.models import GamePicks, PoolSettings, userSeasonPoints

from .factories import create_game, create_league, finish_game, make_pick
from .harness import GradingTestCase


class ScoringWeightsTest(GradingTestCase):

    def test_custom_win_and_tie_points(self):
        league = create_league("alice", "bob", win_points=3, tie_points=1)
        win_game = create_game(1)
        tie_game = create_game(1)
        mnf = create_game(1, mnf=True)

        for game in (win_game, tie_game, mnf):
            make_pick(league.pool, league["alice"], game, "home")
            make_pick(league.pool, league["bob"], game, "away")
        finish_game(win_game, 24, 10)   # home wins
        finish_game(tie_game, 17, 17)   # NFL tie: both picks earn tie_points
        finish_game(mnf, 14, 20)        # away wins

        # yards supplied only because the incidental 4-4 tie walks the whole
        # tiebreaker chain (which fetches actual yards even when nobody
        # predicted any) before landing on co-winners.
        self.run_pipeline(yards=700)

        # alice: 1 win (3) + 1 tie (1) = 4; bob: 1 win (3) + 1 tie (1) = 4.
        self.assertWeek(league.pool, league["alice"], 1, points=4)
        self.assertWeek(league.pool, league["bob"], 1, points=4)

    def test_custom_weekly_winner_bonus(self):
        league = create_league("alice", "bob", weekly_winner_points=10)
        game = create_game(1, mnf=True)
        make_pick(league.pool, league["alice"], game, "home")
        make_pick(league.pool, league["bob"], game, "away")
        finish_game(game, 21, 7)

        self.run_pipeline()

        self.assertWeek(league.pool, league["alice"], 1, points=1, bonus=10, winner=True)
        self.assertStandings(league.pool, [
            (league["alice"], 11, 1),
            (league["bob"], 0, 2),
        ])


class TiebreakerConfigurationTest(GradingTestCase):
    """Non-default chains. Each test: alice and bob tie on pick totals."""

    def _tied_week(self, league, *, alice_tb, bob_tb):
        """One MNF game both users call correctly; tiebreaker guesses vary."""
        mnf = create_game(1, mnf=True)
        make_pick(
            league.pool, league["alice"], mnf, "home",
            score=alice_tb[0], yards=alice_tb[1],
        )
        make_pick(
            league.pool, league["bob"], mnf, "home",
            score=bob_tb[0], yards=bob_tb[1],
        )
        finish_game(mnf, 24, 21)  # total 45
        return mnf

    def test_total_score_without_going_over(self):
        league = create_league(
            "alice", "bob",
            primary_tiebreaker=PoolSettings.PrimaryTiebreaker.TOTAL_SCORE_NO_OVER,
        )
        # Price-is-Right rules: bob is closer (46) but busted by going over;
        # alice (38, under by 7) takes it.
        self._tied_week(league, alice_tb=(38, None), bob_tb=(46, None))

        self.run_pipeline()

        self.assertWeek(league.pool, league["alice"], 1, bonus=2, winner=True)
        self.assertWeek(league.pool, league["bob"], 1, winner=False)

    def test_split_points_divides_the_bonus(self):
        league = create_league(
            "alice", "bob",
            weekly_winner_points=5,
            secondary_tiebreaker=PoolSettings.SecondaryTiebreaker.SPLIT_POINTS,
        )
        # Primary dead heat (40 vs 50 around 45) → split_points is terminal.
        self._tied_week(league, alice_tb=(40, None), bob_tb=(50, None))

        self.run_pipeline()

        rows = userSeasonPoints.objects.filter(pool=league.pool)
        self.assertTrue(all(row.week_1_winner for row in rows))
        bonuses = sorted(row.week_1_bonus for row in rows)
        # An odd bonus splits 3/2 — never lost, never duplicated.
        self.assertEqual(bonuses, [2, 3])
        self.assertEqual(
            sorted(row.total_points for row in rows), [3, 4]
        )

    def test_coin_flip_produces_exactly_one_winner(self):
        league = create_league(
            "alice", "bob",
            secondary_tiebreaker=PoolSettings.SecondaryTiebreaker.COIN_FLIP,
        )
        self._tied_week(league, alice_tb=(40, None), bob_tb=(50, None))

        self.run_pipeline()
        winners = list(
            userSeasonPoints.objects.filter(pool=league.pool, week_1_winner=True)
        )
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners[0].week_1_bonus, 2)

        # The flip is seeded from (pool, season, week): a forced re-award
        # must land on the same person, so re-runs can never flip the result.
        first_winner = winners[0].userID
        from pickem_api.weekly_winners import award_weekly_winners

        result = award_weekly_winners(
            league.pool, league.pool.season, 1,
            stats_provider=self.last_stats_stub, force=True,
        )
        self.assertEqual(result["winners"], [first_winner])

    def test_allow_tiebreaker_off_means_co_winners(self):
        league = create_league("alice", "bob", allow_tiebreaker=False)
        # alice's near-perfect guess must be ignored: the pool turned
        # tiebreakers off, so a points tie is simply shared.
        self._tied_week(league, alice_tb=(45, None), bob_tb=(3, None))

        self.run_pipeline()

        self.assertWeek(league.pool, league["alice"], 1, bonus=2, winner=True)
        self.assertWeek(league.pool, league["bob"], 1, bonus=2, winner=True)


class MissedPickPolicyTest(GradingTestCase):

    def test_auto_home_policy_generates_and_grades_a_home_pick(self):
        league = create_league(
            "alice", "bob",
            missed_pick_policy=PoolSettings.MissedPickPolicy.AUTO_HOME,
        )
        game = create_game(1, mnf=True)
        make_pick(league.pool, league["alice"], game, "away")
        # bob never picks; the game has kicked off (factory kickoffs are in
        # the past), so the policy fills in the home team for him.
        finish_game(game, 28, 14)  # home wins → bob's auto pick is correct

        self.run_pipeline()

        auto = GamePicks.objects.get(
            pool=league.pool, userID=str(league["bob"].id), pick_game_id=game.id
        )
        self.assertTrue(auto.auto_pick)
        self.assertEqual(auto.pick, game.homeTeamSlug)
        self.assertStandings(league.pool, [
            (league["bob"], 3, 1),   # 1 + 2 bonus — the auto pick counts
            (league["alice"], 0, 2),
        ])

    def test_auto_favorite_policy_follows_the_betting_favorite(self):
        league = create_league(
            "alice", "bob",
            missed_pick_policy=PoolSettings.MissedPickPolicy.AUTO_FAVORITE,
        )
        game = create_game(
            1, mnf=True,
            home_win_probability=35.0, away_win_probability=65.0,
        )
        make_pick(league.pool, league["alice"], game, "home")
        finish_game(game, 10, 30)  # the away favorite wins

        self.run_pipeline()

        auto = GamePicks.objects.get(
            pool=league.pool, userID=str(league["bob"].id), pick_game_id=game.id
        )
        self.assertTrue(auto.auto_pick)
        self.assertEqual(auto.pick, game.awayTeamSlug)
        self.assertStandings(league.pool, [
            (league["bob"], 3, 1),
            (league["alice"], 0, 2),
        ])
