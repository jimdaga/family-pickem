from django.core.management.base import BaseCommand

from pickem.utils import get_season
from pickem_api.ai_weekly_summaries import SummarySettings, generate_weekly_summary
from pickem_api.models import Family, Pool
from pickem_api.weekly_winners import latest_complete_week


class Command(BaseCommand):
    help = 'Generate unpublished, commissioner-reviewable AI weekly recap drafts.'

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, default=None)
        parser.add_argument('--week', type=int, default=None)
        parser.add_argument('--pool', type=int, default=None)
        parser.add_argument('--force', action='store_true', help='Regenerate even if a draft already exists.')

    def handle(self, *args, **options):
        # The scheduled command remains observable through JobRun, but avoids
        # creating a database row for every pool every minute while disabled.
        if not SummarySettings.from_django().active:
            self.stdout.write('AI weekly recaps are disabled; no provider calls made.')
            return
        season = options['season'] or get_season()
        week = options['week'] if options['week'] is not None else latest_complete_week(season)
        if week is None:
            self.stdout.write('No completed week yet; nothing to summarize.')
            return
        pools = Pool.objects.filter(status=Pool.Status.ACTIVE, season=season, family__status=Family.Status.ACTIVE)
        if options['pool']:
            pools = pools.filter(id=options['pool'])
        for pool in pools:
            run = generate_weekly_summary(pool, season, week, force=options['force'])
            self.stdout.write(f' - {pool}: {run.status}')
