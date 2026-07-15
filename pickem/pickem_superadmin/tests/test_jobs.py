from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_superadmin import jobs
from pickem_superadmin.models import SuperAdminAuditLog


class RunCommandTests(TestCase):
    def test_rejects_a_command_that_is_not_allowlisted(self):
        """Second defense layer: even if a non-allowlisted job id somehow made
        it into the jobstore, APScheduler's execution-time call into
        run_command() must still refuse to run it -- and must not have called
        call_command at all."""
        with patch('pickem_superadmin.jobs.call_command') as call_command:
            with self.assertRaises(ValueError):
                jobs.run_command('flush')
            call_command.assert_not_called()


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
