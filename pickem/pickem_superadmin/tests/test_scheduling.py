from django.core.exceptions import ValidationError
from django.test import TestCase

from pickem_api.models import ScheduledJobConfig


class ScheduledJobConfigTests(TestCase):
    def test_seed_from_registry_creates_a_row_per_registry_job(self):
        from pickem_api.scheduler import JOB_REGISTRY

        ScheduledJobConfig.objects.all().delete()
        ScheduledJobConfig.seed_from_registry()
        self.assertEqual(
            set(ScheduledJobConfig.objects.values_list('job_id', flat=True)),
            set(JOB_REGISTRY.keys()),
        )

    def test_seed_uses_registry_default_minutes(self):
        ScheduledJobConfig.objects.all().delete()
        ScheduledJobConfig.seed_from_registry()
        cfg = ScheduledJobConfig.objects.get(job_id='update_records')
        self.assertEqual(cfg.interval_minutes, 30)
        self.assertTrue(cfg.enabled)

    def test_seed_is_idempotent_and_preserves_edits(self):
        ScheduledJobConfig.objects.all().delete()
        ScheduledJobConfig.seed_from_registry()
        cfg = ScheduledJobConfig.objects.get(job_id='update_all')
        cfg.interval_minutes = 5
        cfg.save()
        ScheduledJobConfig.seed_from_registry()  # must not reset the edit
        self.assertEqual(
            ScheduledJobConfig.objects.get(job_id='update_all').interval_minutes, 5,
        )

    def test_interval_must_be_at_least_one(self):
        cfg = ScheduledJobConfig(job_id='x', interval_minutes=0)
        with self.assertRaises(ValidationError):
            cfg.full_clean()


class RescheduleLiveTests(TestCase):
    def test_reschedule_live_returns_false_without_a_scheduler(self):
        from pickem_api import scheduler

        original = scheduler._scheduler
        scheduler._scheduler = None
        try:
            self.assertFalse(scheduler.reschedule_live('update_all', 5, True))
        finally:
            scheduler._scheduler = original

    def test_reschedule_live_reregisters_on_a_live_scheduler(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from pickem_api import scheduler

        fake = BackgroundScheduler()
        fake.start(paused=True)
        original = scheduler._scheduler
        scheduler._scheduler = fake
        try:
            self.assertTrue(scheduler.reschedule_live('update_all', 5, True))
            job = fake.get_job('update_all')
            self.assertIsNotNone(job)
            # Disabling removes it entirely.
            self.assertTrue(scheduler.reschedule_live('update_all', 5, False))
            self.assertIsNone(fake.get_job('update_all'))
        finally:
            fake.shutdown(wait=False)
            scheduler._scheduler = original
