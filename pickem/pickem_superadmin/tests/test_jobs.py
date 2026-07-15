from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_superadmin import jobs
from pickem_superadmin.models import SuperAdminAuditLog


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
