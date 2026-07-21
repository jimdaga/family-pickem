from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from pickem_api.models import JobRun, RunningJobMarker, ScheduledJobConfig


class ScheduledJobConfigTests(TestCase):
    def test_seed_creates_a_row_per_orchestrated_job(self):
        from pickem_api.scheduler import JOB_ORDER

        ScheduledJobConfig.objects.all().delete()
        ScheduledJobConfig.seed_from_pipeline()
        self.assertEqual(
            set(ScheduledJobConfig.objects.values_list('job_id', flat=True)),
            set(JOB_ORDER),
        )

    def test_seed_uses_default_minutes(self):
        ScheduledJobConfig.objects.all().delete()
        ScheduledJobConfig.seed_from_pipeline()
        self.assertEqual(ScheduledJobConfig.objects.get(job_id='update_records').interval_minutes, 30)
        self.assertEqual(ScheduledJobConfig.objects.get(job_id='update_stats').interval_minutes, 5)
        self.assertEqual(ScheduledJobConfig.objects.get(job_id='update_games').interval_minutes, 1)

    def test_seed_is_idempotent_and_preserves_edits(self):
        ScheduledJobConfig.objects.all().delete()
        ScheduledJobConfig.seed_from_pipeline()
        ScheduledJobConfig.objects.filter(job_id='update_games').update(interval_minutes=7)
        ScheduledJobConfig.seed_from_pipeline()
        self.assertEqual(ScheduledJobConfig.objects.get(job_id='update_games').interval_minutes, 7)

    def test_interval_must_be_at_least_one(self):
        cfg = ScheduledJobConfig(job_id='x', interval_minutes=0)
        with self.assertRaises(ValidationError):
            cfg.full_clean()

    def test_is_due(self):
        now = timezone.now()
        cfg = ScheduledJobConfig(job_id='x', interval_minutes=10, last_run_at=None)
        self.assertTrue(cfg.is_due(now))  # never run
        cfg.last_run_at = now - timedelta(minutes=5)
        self.assertFalse(cfg.is_due(now))  # 5 < 10
        cfg.last_run_at = now - timedelta(minutes=15)
        self.assertTrue(cfg.is_due(now))  # 15 >= 10


class RunJobOnceTests(TestCase):
    def setUp(self):
        ScheduledJobConfig.seed_from_pipeline()

    def test_records_jobrun_updates_config_and_clears_marker(self):
        from pickem_api import scheduler

        ran = []
        scheduler.run_job_once('update_picks', run=lambda: ran.append('x'))

        self.assertEqual(ran, ['x'])
        run = JobRun.objects.get(job_id='update_picks')
        self.assertEqual(run.status, JobRun.Status.SUCCESS)
        self.assertIsNotNone(run.finished_at)
        self.assertIsNotNone(ScheduledJobConfig.objects.get(job_id='update_picks').last_run_at)
        self.assertFalse(RunningJobMarker.objects.filter(job_id='update_picks').exists())

    def test_captures_failure_without_raising(self):
        from pickem_api import scheduler

        def boom():
            raise RuntimeError('nope')

        scheduler.run_job_once('update_games', run=boom)  # must not raise
        run = JobRun.objects.get(job_id='update_games')
        self.assertEqual(run.status, JobRun.Status.ERROR)
        self.assertIn('RuntimeError', run.exception)

    def test_log_context_set_during_run_and_cleared_after(self):
        from pickem_api import scheduler

        seen = {}
        scheduler.run_job_once('update_stats', run=lambda: seen.update(ctx=scheduler.current_log_context()))
        run_id, job_id = seen['ctx']
        self.assertIsNotNone(run_id)
        self.assertEqual(job_id, 'update_stats')
        self.assertEqual(scheduler.current_log_context(), (None, None))

    @patch('pickem_homepage.emailing.send_due_email_campaigns')
    def test_scheduled_email_campaign_runner_needs_no_job_argument(self, send_campaigns):
        from pickem_api import scheduler

        scheduler.run_job_once(
            'send_scheduled_email_campaigns',
            run=scheduler._RUN_BY_ID['send_scheduled_email_campaigns'],
        )

        send_campaigns.assert_called_once_with()
        self.assertEqual(
            JobRun.objects.get(job_id='send_scheduled_email_campaigns').status,
            JobRun.Status.SUCCESS,
        )


class PipelineTickTests(TestCase):
    def setUp(self):
        ScheduledJobConfig.seed_from_pipeline()

    def test_runs_due_enabled_jobs_in_dependency_order(self):
        from pickem_api import scheduler

        # Disable one step; make update_records not due (it just ran).
        ScheduledJobConfig.objects.filter(job_id='update_stats').update(enabled=False)
        ScheduledJobConfig.objects.filter(job_id='update_records').update(last_run_at=timezone.now())

        ran = []
        with patch.object(scheduler, 'run_job_once', side_effect=lambda jid, run=None: ran.append(jid)):
            scheduler.run_pipeline_tick()

        self.assertNotIn('update_records', ran)   # not due
        self.assertNotIn('update_stats', ran)     # disabled
        self.assertIn('update_games', ran)
        self.assertIn('update_picks', ran)
        # Dependency order preserved.
        self.assertLess(ran.index('update_games'), ran.index('update_picks'))
        self.assertLess(ran.index('update_picks'), ran.index('update_standings'))
