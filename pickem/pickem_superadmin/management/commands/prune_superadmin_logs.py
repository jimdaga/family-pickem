"""Age out SuperAdminLogEntry rows: delete anything older than LOG_RETENTION_DAYS,
then trim to the newest LOG_MAX_ROWS. Queueable from the jobs page and registered
as a daily scheduler job."""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from pickem_superadmin.models import SuperAdminLogEntry


class Command(BaseCommand):
    help = 'Delete old/excess superadmin log entries.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.LOG_RETENTION_DAYS)
        by_age, _ = SuperAdminLogEntry.objects.filter(timestamp__lt=cutoff).delete()

        by_cap = 0
        max_rows = settings.LOG_MAX_ROWS
        total = SuperAdminLogEntry.objects.count()
        if total > max_rows:
            overflow_ids = list(
                SuperAdminLogEntry.objects.order_by('-timestamp')
                .values_list('id', flat=True)[max_rows:]
            )
            by_cap, _ = SuperAdminLogEntry.objects.filter(id__in=overflow_ids).delete()

        self.stdout.write(f'Pruned {by_age} by age, {by_cap} by row cap.')
