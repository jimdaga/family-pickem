from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pickem_api.models import ScheduledJobConfig
from pickem_superadmin import jobs
from pickem_superadmin.models import SuperAdminAuditLog


class SchedulerHealthTests(TestCase):
    def test_dead_scheduler_with_no_history_reads_as_not_alive(self):
        # No executions, no registered jobs -> nothing is scheduling.
        health = jobs.scheduler_health()
        self.assertFalse(health['alive'])

    def test_fresh_deploy_with_a_scheduled_job_reads_as_alive(self):
        """A live scheduler on a fresh deploy has registered jobs (future
        next_run_time) but no execution history yet. It must not be blocked from
        queueing the first manual run."""
        from django_apscheduler.models import DjangoJob

        DjangoJob.objects.create(
            id='update_all', next_run_time=timezone.now() + timedelta(seconds=30),
        )
        health = jobs.scheduler_health()
        self.assertTrue(health['alive'])

    def test_stale_next_run_time_with_no_history_reads_as_not_alive(self):
        from django_apscheduler.models import DjangoJob

        DjangoJob.objects.create(
            id='update_all', next_run_time=timezone.now() - timedelta(hours=1),
        )
        health = jobs.scheduler_health()
        self.assertFalse(health['alive'])


class RunCommandTests(TestCase):
    def test_rejects_a_command_that_is_not_allowlisted(self):
        """Second defense layer: even if a non-allowlisted job id somehow made
        it into the jobstore, APScheduler's execution-time call into
        run_command() must still refuse to run it -- and must not have called
        call_command at all."""
        with patch('pickem_api.scheduler.run_job_once') as runner:
            with self.assertRaises(ValueError):
                jobs.run_command('flush')
            runner.assert_not_called()


class QueueCommandTests(TestCase):
    def test_rejects_a_command_that_is_not_allowlisted(self):
        """Never let a POST body name an arbitrary management command."""
        with self.assertRaises(ValueError):
            jobs.queue_command('flush')

    @patch('pickem_superadmin.jobs.get_scheduler')
    def test_queues_an_allowlisted_command_as_a_one_off_job(self, get_scheduler):
        job_id = jobs.queue_command('update_standings')

        scheduler = get_scheduler.return_value
        scheduler.add_job.assert_called_once()
        kwargs = scheduler.add_job.call_args.kwargs
        self.assertEqual(kwargs['args'], ['update_standings'])
        self.assertEqual(kwargs['trigger'], 'date')
        self.assertTrue(job_id.startswith('manual:update_standings:'))

    def test_queue_command_actually_persists_a_job_row_on_a_web_worker(self):
        """End-to-end, no mocking of get_scheduler/queue_command: on a plain web
        worker (no live in-process scheduler), queue_command must leave a row in
        the DjangoJobStore's table. Before the fix, the fallback scheduler was
        never started, so add_job() only appended to an in-memory list on an
        object that got garbage-collected -- zero rows were ever written, and
        the queued job would silently never run."""
        from django_apscheduler.models import DjangoJob

        from pickem_api import scheduler as scheduler_module

        original_scheduler = scheduler_module._scheduler
        scheduler_module._scheduler = None
        try:
            before = DjangoJob.objects.count()
            job_id = jobs.queue_command('update_standings')
            self.assertTrue(
                DjangoJob.objects.filter(id=job_id).exists(),
                'queue_command() did not persist a DjangoJob row for the '
                'queued job -- it would silently never run.',
            )
            self.assertEqual(DjangoJob.objects.count(), before + 1)
        finally:
            scheduler_module._scheduler = original_scheduler


class JobsPageTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.client.force_login(self.root)

    def test_page_renders(self):
        self.assertEqual(self.client.get(reverse('superadmin:jobs')).status_code, 200)

    @patch('pickem_superadmin.views.jobs.jobs.queue_command')
    @patch('pickem_superadmin.views.jobs.jobs.scheduler_health')
    def test_queueing_a_job_audits_it(self, health, queue_command):
        health.return_value = {'alive': True, 'last_run': None, 'last_status': None, 'stale': False}
        queue_command.return_value = 'manual:update_standings:123'

        self.client.post(
            reverse('superadmin:jobs_queue'), {'command': 'update_standings'},
        )

        queue_command.assert_called_once_with('update_standings')
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.JOB_QUEUED)
        self.assertIn('update_standings', entry.summary)

    @patch('pickem_superadmin.views.jobs.jobs.queue_command')
    @patch('pickem_superadmin.views.jobs.jobs.scheduler_health')
    def test_refuses_to_queue_when_no_scheduler_is_alive(self, health, queue_command):
        """Otherwise the job sits in the jobstore forever and the operator never
        learns why nothing happened."""
        health.return_value = {'alive': False, 'last_run': None, 'last_status': None, 'stale': True}

        response = self.client.post(
            reverse('superadmin:jobs_queue'), {'command': 'update_standings'}, follow=True,
        )

        queue_command.assert_not_called()
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)
        self.assertContains(response, 'no live scheduler')

    @patch('pickem_superadmin.views.jobs.jobs.scheduler_health')
    def test_rejects_a_command_outside_the_allowlist(self, health):
        health.return_value = {'alive': True, 'last_run': None, 'last_status': None, 'stale': False}
        self.client.post(reverse('superadmin:jobs_queue'), {'command': 'flush'})
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)


class JobsStatusEndpointTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root2', email='root2@example.com', password='pw',
        )
        self.client.force_login(self.root)

    def test_status_json_reports_running_jobs(self):
        from pickem_api import scheduler

        scheduler.mark_job_started('update_all')
        data = self.client.get(reverse('superadmin:jobs_status')).json()
        self.assertEqual([r['job_id'] for r in data['running']], ['update_all'])
        self.assertIn('health', data)

    def test_status_json_empty_when_idle(self):
        data = self.client.get(reverse('superadmin:jobs_status')).json()
        self.assertEqual(data['running'], [])


class ScheduleEditTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        ScheduledJobConfig.seed_from_pipeline()
        self.client.force_login(self.root)

    def _post(self, cfg, **overrides):
        data = {
            f'{cfg.pk}-interval_minutes': cfg.interval_minutes,
            f'{cfg.pk}-enabled': 'on' if cfg.enabled else '',
            f'{cfg.pk}-updated_at': cfg.updated_at.isoformat(),
        }
        data.update(overrides)
        return self.client.post(reverse('superadmin:jobs_schedule_save'), data)

    def test_editing_the_interval_persists_and_audits(self):
        cfg = ScheduledJobConfig.objects.get(job_id='update_games')
        self._post(cfg, **{f'{cfg.pk}-interval_minutes': 5})
        cfg.refresh_from_db()
        self.assertEqual(cfg.interval_minutes, 5)
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.SCHEDULE_UPDATED)
        self.assertEqual(entry.changes['interval_minutes'], [1, 5])

    def test_interval_below_one_is_rejected(self):
        cfg = ScheduledJobConfig.objects.get(job_id='update_games')
        self._post(cfg, **{f'{cfg.pk}-interval_minutes': 0})
        cfg.refresh_from_db()
        self.assertEqual(cfg.interval_minutes, 1)  # unchanged

    def test_disabling_a_job_persists(self):
        cfg = ScheduledJobConfig.objects.get(job_id='update_records')
        self._post(cfg, **{f'{cfg.pk}-enabled': ''})
        cfg.refresh_from_db()
        self.assertFalse(cfg.enabled)
