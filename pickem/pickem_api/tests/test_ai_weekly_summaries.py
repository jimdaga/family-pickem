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
from pickem_api.models import Family, FamilyMembership, GamesAndScores, Pool, userSeasonPoints
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

        self.assertEqual(facts['pool']['standings'], [{'member': 'Sam', 'rank': 1, 'total_points': 8, 'week_points': 4, 'week_winner': False}])
        self.assertEqual(facts['results'][0]['winner'], 'Home')
        self.assertNotIn('Jo', str(facts))

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
        self.assertIn('did not tiptoe into the room', second.publication.body)

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
