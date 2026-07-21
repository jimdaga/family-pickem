from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from pickem_api import scheduler as pickem_scheduler
from pickem_api import weekly_winners
from pickem_api.ai_weekly_summaries import (
    SummarySettings, _output_text_from_response, _provider_request, build_summary_facts, generate_weekly_summary,
)
from pickem_api.management.commands import update_season_winners as update_season_winners_cmd
from pickem_api.management.commands.update_all import PIPELINE as UPDATE_ALL_PIPELINE
from pickem_api.models import Family, FamilyMembership, GamePicks, GamesAndScores, Pool, userSeasonPoints
from pickem_homepage.models import AIWeeklySummaryRun, FamilyPublication
from pickem_superadmin.models import AIProviderSettings


def _make_config(retries=2):
    return SummarySettings(
        enabled=True, api_key='sk-test', model='gpt-4o-mini',
        timeout=30, retries=retries, max_runs=3, mock=False,
    )


class AIWeeklySummaryTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Smith', slug='smith')
        self.pool = Pool.objects.create(family=self.family, name='2026', slug='2026', season=2627)
        self.user = User.objects.create_user('sam', 'sam@example.com', 'password', first_name='Sam')
        FamilyMembership.objects.create(family=self.family, user=self.user)
        userSeasonPoints.objects.create(pool=self.pool, userID=str(self.user.id), gameseason=2627, total_points=8, week_1_points=4, current_rank=1)
        GamesAndScores.objects.create(
            id=10001, slug='a-at-h', competition='1', gameWeek='1', gameyear='2026', gameseason=2627,
            startTimestamp='2026-09-10T17:00:00Z', statusType='finished', statusTitle='Final',
            homeTeamId=1, homeTeamSlug='home', homeTeamName='Home', homeTeamScore=21,
            awayTeamId=2, awayTeamSlug='away', awayTeamName='Away', awayTeamScore=17,
            gameWinner='Home', gameScored=True,
        )

    def test_facts_are_deterministic_and_pool_scoped(self):
        other_family = Family.objects.create(name='Jones', slug='jones')
        other_pool = Pool.objects.create(family=other_family, name='2026', slug='2026', season=2627)
        other_user = User.objects.create_user('jo', 'jo@example.com', 'password')
        FamilyMembership.objects.create(family=other_family, user=other_user)
        userSeasonPoints.objects.create(pool=other_pool, userID=str(other_user.id), gameseason=2627, total_points=99, week_1_points=9, current_rank=1)

        facts = build_summary_facts(self.pool, 2627, 1)

        self.assertEqual(facts['pool']['standings'], [{
            'member': 'sam', 'rank': 1, 'previous_rank': 1, 'rank_change': 0,
            'total_points': 8, 'week_points': 4, 'week_winner': False, 'points_behind_next': 0,
        }])
        self.assertEqual(facts['results'][0]['winner'], 'Home')
        self.assertNotIn('jo', str(facts))

    def test_reads_standard_responses_output_content(self):
        self.assertEqual(
            _output_text_from_response({'output': [{'content': [{'type': 'output_text', 'text': 'Real recap'}]}]}),
            'Real recap',
        )

    @override_settings(OPENAI_WEEKLY_SUMMARIES_ENABLED=False, OPENAI_API_KEY='not-used')
    @patch('pickem_api.ai_weekly_summaries.requests.post')
    def test_disabled_configuration_does_not_call_provider(self, post):
        run = generate_weekly_summary(self.pool, 2627, 1)

        self.assertEqual(run.status, AIWeeklySummaryRun.Status.DISABLED)
        self.assertFalse(post.called)
        self.assertFalse(FamilyPublication.objects.exists())

    @override_settings(
        OPENAI_WEEKLY_SUMMARIES_ENABLED=True,
        OPENAI_WEEKLY_SUMMARIES_MOCK=True,
        OPENAI_API_KEY='',
    )
    def test_regeneration_reuses_the_single_ai_publication_slot(self):
        first = generate_weekly_summary(self.pool, 2627, 1, force=True)
        second = generate_weekly_summary(self.pool, 2627, 1, force=True)

        self.assertEqual(first.status, AIWeeklySummaryRun.Status.SUCCESS)
        self.assertEqual(second.status, AIWeeklySummaryRun.Status.SUCCESS)
        self.assertEqual(
            FamilyPublication.objects.filter(
                pool=self.pool, source=FamilyPublication.Source.AI_WEEKLY_SUMMARY,
            ).count(),
            1,
        )
        self.assertEqual(second.publication_id, first.publication_id)
        self.assertIn('Did NOT tiptoe in', second.publication.body)

    @override_settings(
        OPENAI_WEEKLY_SUMMARIES_ENABLED=True,
        OPENAI_WEEKLY_SUMMARIES_MOCK=True,
        OPENAI_WEEKLY_SUMMARIES_MAX_RUNS_PER_POOL_WEEK=1,
        OPENAI_API_KEY='',
    )
    def test_forced_regeneration_bypasses_automatic_run_cap(self):
        first = generate_weekly_summary(self.pool, 2627, 1, force=True)
        second = generate_weekly_summary(self.pool, 2627, 1, force=True)

        self.assertEqual(first.status, AIWeeklySummaryRun.Status.SUCCESS)
        self.assertEqual(second.status, AIWeeklySummaryRun.Status.SUCCESS)

    @override_settings(OPENAI_WEEKLY_SUMMARIES_MOCK=True)
    def test_saved_provider_key_overrides_stale_mock_environment_flag(self):
        provider_settings = AIProviderSettings.load()
        provider_settings.enabled = True
        provider_settings.set_api_key('sk-test-real-provider-key')
        provider_settings.save()

        config = SummarySettings.from_django()

        self.assertTrue(config.active)
        self.assertFalse(config.mock)

    @override_settings(
        OPENAI_WEEKLY_SUMMARIES_ENABLED=True,
        OPENAI_WEEKLY_SUMMARIES_MOCK=True,
        OPENAI_API_KEY='',
    )
    def test_mock_preview_can_use_an_unscored_week(self):
        GamesAndScores.objects.filter(id=10001).update(gameScored=False)

        run = generate_weekly_summary(self.pool, 2627, 1, force=True, preview=True)

        self.assertEqual(run.status, AIWeeklySummaryRun.Status.SUCCESS)
        self.assertEqual(run.publication.title, 'Week 1 recap (preview)')

    def test_facts_include_pool_rules_from_pool_settings(self):
        from pickem_api.models import PoolSettings

        PoolSettings.objects.create(
            pool=self.pool,
            weekly_winner_points=7,
            primary_tiebreaker=PoolSettings.PrimaryTiebreaker.COMBINED_YARDS,
            secondary_tiebreaker=PoolSettings.SecondaryTiebreaker.COIN_FLIP,
            allow_tiebreaker=True,
            missed_pick_policy=PoolSettings.MissedPickPolicy.AUTO_HOME,
            pick_type=PoolSettings.PickType.STRAIGHT_UP,
        )

        facts = build_summary_facts(self.pool, 2627, 1)

        self.assertEqual(facts['pool_rules'], {
            'weekly_winner_points': 7,
            'primary_tiebreaker': 'combined_yards',
            'secondary_tiebreaker': 'coin_flip',
            'allow_tiebreaker': True,
            'missed_pick_policy': 'auto_home',
            'pick_type': 'straight_up',
        })

    def test_facts_use_default_pool_rules_when_unconfigured(self):
        facts = build_summary_facts(self.pool, 2627, 1)

        self.assertEqual(facts['pool_rules']['weekly_winner_points'], 2)
        self.assertFalse(facts['is_final_week'])
        self.assertEqual(facts['season_champion'], [])

    @override_settings(
        OPENAI_WEEKLY_SUMMARIES_ENABLED=True,
        OPENAI_WEEKLY_SUMMARIES_MOCK=True,
        OPENAI_API_KEY='',
    )
    def test_mock_preview_calls_out_season_champion_when_present(self):
        userSeasonPoints.objects.filter(pool=self.pool, userID=str(self.user.id)).update(
            week_18_points=10, week_18_winner=True, year_winner=True,
        )
        GamesAndScores.objects.create(
            id=10002, slug='b-at-h', competition='1', gameWeek='18', gameyear='2026', gameseason=2627,
            startTimestamp='2026-12-30T17:00:00Z', statusType='finished', statusTitle='Final',
            homeTeamId=3, homeTeamSlug='home2', homeTeamName='Home2', homeTeamScore=14,
            awayTeamId=4, awayTeamSlug='away2', awayTeamName='Away2', awayTeamScore=10,
            gameWinner='Home2', gameScored=True,
        )

        run = generate_weekly_summary(self.pool, 2627, 18, force=True)

        self.assertEqual(run.status, AIWeeklySummaryRun.Status.SUCCESS)
        self.assertIn('sam', run.publication.body)
        self.assertIn('champion', run.publication.body.lower())

    @override_settings(
        OPENAI_WEEKLY_SUMMARIES_ENABLED=True,
        OPENAI_WEEKLY_SUMMARIES_MOCK=True,
        OPENAI_API_KEY='',
    )
    def test_mock_preview_does_not_crown_a_champion_on_a_non_final_week(self):
        # year_winner reflects season-wide state and can already be True
        # (e.g. regenerating an earlier week's draft after the season ended).
        # Only week 18's own recap should get the finale treatment.
        userSeasonPoints.objects.filter(pool=self.pool, userID=str(self.user.id)).update(
            year_winner=True,
        )

        run = generate_weekly_summary(self.pool, 2627, 1, force=True)

        self.assertEqual(run.status, AIWeeklySummaryRun.Status.SUCCESS)
        self.assertNotIn('champion', run.publication.body.lower())


class FactsSeasonChampionTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Smith', slug='smith')
        self.pool = Pool.objects.create(family=self.family, name='2026', slug='2026', season=2627)
        self.user = User.objects.create_user('sam', 'sam@example.com', 'password', first_name='Sam')
        FamilyMembership.objects.create(family=self.family, user=self.user)
        GamesAndScores.objects.create(
            id=20001, slug='a-at-h', competition='1', gameWeek='18', gameyear='2026', gameseason=2627,
            startTimestamp='2026-12-30T17:00:00Z', statusType='finished', statusTitle='Final',
            homeTeamId=1, homeTeamSlug='home', homeTeamName='Home', homeTeamScore=21,
            awayTeamId=2, awayTeamSlug='away', awayTeamName='Away', awayTeamScore=17,
            gameWinner='Home', gameScored=True,
        )

    def test_season_champion_present_when_year_winner_flagged(self):
        userSeasonPoints.objects.create(
            pool=self.pool, userID=str(self.user.id), gameseason=2627,
            total_points=100, week_18_points=10, week_18_winner=True,
            year_winner=True, current_rank=1,
        )

        facts = build_summary_facts(self.pool, 2627, 18)

        self.assertTrue(facts['is_final_week'])
        self.assertEqual(facts['season_champion'], ['sam'])

    def test_season_champion_empty_before_year_winner_is_flagged(self):
        userSeasonPoints.objects.create(
            pool=self.pool, userID=str(self.user.id), gameseason=2627,
            total_points=100, week_18_points=10, week_18_winner=True,
            year_winner=False, current_rank=1,
        )

        facts = build_summary_facts(self.pool, 2627, 18)

        self.assertTrue(facts['is_final_week'])
        self.assertEqual(facts['season_champion'], [])


class ProviderRetryTests(TestCase):
    @patch('pickem_api.ai_weekly_summaries.requests.post')
    def test_4xx_response_is_not_retried(self, post):
        response = MagicMock(status_code=401)
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        post.return_value = response

        with self.assertRaises(RuntimeError):
            _provider_request(_make_config(retries=2), {'week': 1})

        self.assertEqual(post.call_count, 1)

    @patch('pickem_api.ai_weekly_summaries.requests.post')
    def test_5xx_response_is_retried_up_to_the_configured_limit(self, post):
        response = MagicMock(status_code=503)
        post.return_value = response

        with self.assertRaises(RuntimeError):
            _provider_request(_make_config(retries=2), {'week': 1})

        self.assertEqual(post.call_count, 3)  # 1 initial + 2 retries

    @patch('pickem_api.ai_weekly_summaries.requests.post')
    def test_network_error_is_retried(self, post):
        post.side_effect = requests.ConnectionError('boom')

        with self.assertRaises(RuntimeError):
            _provider_request(_make_config(retries=1), {'week': 1})

        self.assertEqual(post.call_count, 2)  # 1 initial + 1 retry


class FinalWeekConstantTests(TestCase):
    def test_final_week_constant_is_shared(self):
        self.assertEqual(weekly_winners.FINAL_WEEK, 18)
        self.assertIs(update_season_winners_cmd.FINAL_WEEK, weekly_winners.FINAL_WEEK)


class PipelineOrderTests(TestCase):
    def test_update_all_generates_summaries_after_season_winners(self):
        self.assertLess(
            UPDATE_ALL_PIPELINE.index('update_season_winners'),
            UPDATE_ALL_PIPELINE.index('generate_weekly_summaries'),
        )

    def test_scheduler_generates_summaries_after_season_winners(self):
        job_ids = [job_id for job_id, _label, _mins in pickem_scheduler.PIPELINE]
        self.assertLess(
            job_ids.index('update_season_winners'),
            job_ids.index('generate_weekly_summaries'),
        )


class NotablePicksAndStandingsMovementTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Rivals', slug='rivals')
        self.pool = Pool.objects.create(family=self.family, name='2026', slug='2026', season=2627)
        self.alice = User.objects.create_user('alice', 'alice@example.com', 'password', first_name='Alice')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'password', first_name='Bob')
        self.carol = User.objects.create_user('carol', 'carol@example.com', 'password', first_name='Carol')
        for user in (self.alice, self.bob, self.carol):
            FamilyMembership.objects.create(family=self.family, user=user)

        GamesAndScores.objects.create(
            id=20001, slug='raiders-at-chiefs', competition='1', gameWeek='2', gameyear='2026', gameseason=2627,
            startTimestamp='2026-09-17T17:00:00Z', statusType='finished', statusTitle='Final',
            homeTeamId=1, homeTeamSlug='chiefs', homeTeamName='Kansas City Chiefs', homeTeamScore=17,
            awayTeamId=2, awayTeamSlug='raiders', awayTeamName='Las Vegas Raiders', awayTeamScore=20,
            gameWinner='raiders', gameScored=True, spread=7.0,
        )
        GamesAndScores.objects.create(
            id=20002, slug='dolphins-at-jets', competition='1', gameWeek='2', gameyear='2026', gameseason=2627,
            startTimestamp='2026-09-17T20:00:00Z', statusType='finished', statusTitle='Final',
            homeTeamId=3, homeTeamSlug='jets', homeTeamName='New York Jets', homeTeamScore=24,
            awayTeamId=4, awayTeamSlug='dolphins', awayTeamName='Miami Dolphins', awayTeamScore=10,
            gameWinner='jets', gameScored=True, spread=2.0,
        )

        picks = [
            (self.alice, 20001, 'chiefs', False),   # picked the favorite; favorite lost -> bad beat
            (self.bob, 20001, 'raiders', True),      # picked the underdog correctly -> upset call
            (self.carol, 20001, 'raiders', True),    # also correct -- not a lonely correct pick
            (self.alice, 20002, 'dolphins', False),
            (self.bob, 20002, 'dolphins', False),
            (self.carol, 20002, 'jets', True),        # only correct pick on this game -> lonely correct
        ]
        for user, game_id, pick, correct in picks:
            GamePicks.objects.create(
                id=f'{self.pool.id}-{user.id}-{game_id}', pool=self.pool, pick_game_id=game_id,
                slug=str(game_id), userID=str(user.id), uid=user.id, userEmail=user.email,
                gameWeek='2', gameyear='2026', gameseason=2627, competition='1',
                pick=pick, pick_correct=correct,
            )

        userSeasonPoints.objects.create(
            pool=self.pool, userID=str(self.alice.id), gameseason=2627, current_rank=3,
            total_points=10, week_2_points=3, week_2_bonus=0,
        )
        userSeasonPoints.objects.create(
            pool=self.pool, userID=str(self.bob.id), gameseason=2627, current_rank=1,
            total_points=12, week_2_points=1, week_2_bonus=0,
        )
        userSeasonPoints.objects.create(
            pool=self.pool, userID=str(self.carol.id), gameseason=2627, current_rank=2,
            total_points=11, week_2_points=6, week_2_bonus=0,
        )

    def test_results_and_picks_resolve_team_slugs_to_display_names(self):
        facts = build_summary_facts(self.pool, 2627, 2)

        winners = {f"{r['home_team']}-{r['away_team']}": r['winner'] for r in facts['results']}
        self.assertEqual(winners['Kansas City Chiefs-Las Vegas Raiders'], 'Las Vegas Raiders')
        self.assertEqual(winners['New York Jets-Miami Dolphins'], 'New York Jets')

        alice_picks = next(m for m in facts['pool']['member_pick_results'] if m['member'] == 'alice')
        picked_teams = {p['game_id']: p['pick_team'] for p in alice_picks['picks']}
        self.assertEqual(picked_teams[20001], 'Kansas City Chiefs')
        self.assertEqual(picked_teams[20002], 'Miami Dolphins')

    def test_standings_include_rank_movement_and_gap_to_next(self):
        facts = build_summary_facts(self.pool, 2627, 2)

        by_member = {s['member']: s for s in facts['pool']['standings']}
        self.assertEqual(by_member['bob'], {
            'member': 'bob', 'rank': 1, 'previous_rank': 1, 'rank_change': 0,
            'total_points': 12, 'week_points': 1, 'week_winner': False, 'points_behind_next': 0,
        })
        self.assertEqual(by_member['carol']['rank_change'], 1)
        self.assertEqual(by_member['carol']['points_behind_next'], 1)
        self.assertEqual(by_member['alice']['rank_change'], -1)
        self.assertEqual(by_member['alice']['points_behind_next'], 1)

    def test_notable_picks_identify_lonely_correct_and_upset_patterns(self):
        facts = build_summary_facts(self.pool, 2627, 2)

        notable = facts['notable_picks']
        self.assertEqual(notable['lonely_correct'], [
            {'member': 'carol', 'team': 'New York Jets', 'total_pickers': 3},
        ])
        self.assertEqual(notable['upset_calls'], [
            {'member': 'bob', 'team': 'Las Vegas Raiders', 'spread': 7.0},
            {'member': 'carol', 'team': 'Las Vegas Raiders', 'spread': 7.0},
        ])
        self.assertEqual(notable['bad_beats'], [
            {'member': 'alice', 'team': 'Kansas City Chiefs', 'spread': 7.0},
        ])

    def test_small_spread_does_not_produce_upset_signals(self):
        # The jets/dolphins game has a 2.0 spread, below the 3.0 threshold,
        # even though jets (the favorite) won -- no upset either way here,
        # but this confirms a small spread never contributes bad_beats/upset_calls.
        facts = build_summary_facts(self.pool, 2627, 2)

        teams_in_upsets = {entry['team'] for entry in facts['notable_picks']['upset_calls'] + facts['notable_picks']['bad_beats']}
        self.assertNotIn('New York Jets', teams_in_upsets)
        self.assertNotIn('Miami Dolphins', teams_in_upsets)
