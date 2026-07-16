from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from pickem_api import scheduler
from pickem_api.models import RunningJobMarker


class RunningMarkerTests(TestCase):
    def test_start_then_finish_clears_the_marker(self):
        scheduler.mark_job_started('update_all')
        self.assertEqual(len(scheduler.current_running_jobs()), 1)
        scheduler.mark_job_finished('update_all')
        self.assertEqual(scheduler.current_running_jobs(), [])

    def test_start_is_idempotent_per_job(self):
        scheduler.mark_job_started('update_all')
        scheduler.mark_job_started('update_all')
        self.assertEqual(RunningJobMarker.objects.filter(job_id='update_all').count(), 1)

    def test_stale_markers_are_not_reported_running(self):
        RunningJobMarker.objects.create(
            job_id='update_all',
            started_at=timezone.now() - timedelta(minutes=30),
        )
        self.assertEqual(scheduler.current_running_jobs(), [])
