"""Calculate and store per-pool user rankings for a season.

ORM-based, pool-aware replacement for ``cron_update_rankings.py``. The old
script ranked every ``userSeasonPoints`` row for the season together, mixing
users across pools; under the multi-tenant model rankings must be scoped to
each pool. Users are ranked by ``total_points`` (descending) with standard
competition tie handling (1, 1, 3, ...); the result is stored in
``current_rank``.

Run after ``update_standings`` so rankings reflect the latest point totals.
"""

import logging

from django.core.management.base import BaseCommand

from pickem.utils import get_season
from pickem_api.models import userSeasonPoints

logger = logging.getLogger(__name__)


def calculate_pool_rankings(gameseason, pool_id):
    """Rank users within a single pool for the season. Returns the count ranked."""
    users = list(
        userSeasonPoints.objects.filter(
            gameseason=gameseason, pool_id=pool_id
        ).order_by("-total_points", "userEmail")
    )
    if not users:
        return 0

    current_rank = 1
    users_at_current_rank = 0
    previous_points = None

    for entry in users:
        points = entry.total_points or 0
        if previous_points is not None and points < previous_points:
            current_rank += users_at_current_rank
            users_at_current_rank = 0
        entry.current_rank = current_rank
        entry.save(update_fields=["current_rank"])
        users_at_current_rank += 1
        previous_points = points

    return len(users)


class Command(BaseCommand):
    help = "Calculate per-pool user rankings (current_rank) for a season."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="Season in YYZZ format (defaults to the current season).",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        self.stdout.write(f"Calculating rankings for season {season}")

        pool_ids = (
            userSeasonPoints.objects.filter(gameseason=season)
            # order_by() clears Meta.ordering (total_points), which would
            # otherwise leak into the SELECT and break DISTINCT on pool_id.
            .order_by()
            .values_list("pool_id", flat=True)
            .distinct()
        )

        total_ranked = 0
        pools_done = 0
        for pool_id in pool_ids:
            ranked = calculate_pool_rankings(season, pool_id)
            if ranked:
                pools_done += 1
                total_ranked += ranked
                self.stdout.write(f" - pool {pool_id}: ranked {ranked} users")

        self.stdout.write(
            self.style.SUCCESS(
                f"Ranked {total_ranked} users across {pools_done} pools."
            )
        )
