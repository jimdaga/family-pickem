"""Flag families that have gone idle, and clear the flag when they come back.

A family is idle when no member made a manual pick (``auto_pick=False``) in
either of the last two completed NFL weeks of the current season. Any manual
pick in those weeks, or in any later week of the season (picking ahead for the
upcoming week counts), makes it active again.

Deliberately conservative about *setting* the flag:
  * fewer than two completed weeks (preseason / offseason / week 1) -> nobody
    is newly flagged; existing flags persist across the season rollover, so a
    family that went quiet stays idle until a member picks on their own;
  * families created within the grace window are never flagged — a brand-new
    family hasn't had two weeks to play yet.

Only lifecycle-active families are evaluated (``status=INACTIVE`` is the
commissioner soft-delete, a separate concept). ``Family.is_idle`` gates the
weekly "picks are ready" email. Runs from the update pipeline.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from pickem.utils import get_season
from pickem_api.models import Family, FamilyAuditLog, GamePicks
from pickem_api.weekly_winners import complete_weeks

logger = logging.getLogger(__name__)

IDLE_AFTER_WEEKS = 2
NEW_FAMILY_GRACE = timedelta(days=14)


def active_family_ids(season, since_week, competition='nfl'):
    """Ids of families with a manual pick in ``since_week`` or later."""
    weeks = [str(week) for week in range(since_week, 19)]
    return set(
        GamePicks.objects.filter(
            gameseason=season,
            competition=competition,
            gameWeek__in=weeks,
            auto_pick=False,
            pool__isnull=False,
        )
        .order_by()
        .values_list('pool__family_id', flat=True)
        .distinct()
    )


class Command(BaseCommand):
    help = "Mark families idle/active from recent pick activity."

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, default=None)
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report changes without saving them.",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        dry_run = options["dry_run"]
        now = timezone.now()

        completed = complete_weeks(season)
        can_judge = len(completed) >= IDLE_AFTER_WEEKS
        if can_judge:
            since_week = completed[-IDLE_AFTER_WEEKS]
        else:
            # Can't flag anyone yet; still clear flags for any family picking
            # this season.
            since_week = 1
        active_ids = active_family_ids(season, since_week)

        went_idle, came_back = [], []
        for family in Family.objects.filter(status=Family.Status.ACTIVE):
            if family.id in active_ids:
                if family.is_idle:
                    came_back.append(family)
            elif (
                can_judge
                and not family.is_idle
                and family.created_at <= now - NEW_FAMILY_GRACE
            ):
                went_idle.append(family)

        if not dry_run:
            for family, idle in [(f, True) for f in went_idle] + [(f, False) for f in came_back]:
                family.is_idle = idle
                family.idle_since = now if idle else None
                family.save(update_fields=['is_idle', 'idle_since', 'updated_at'])
                # Flips gate the weekly email, so leave a trail in the
                # family's own audit log (actor=None: the pipeline did it).
                FamilyAuditLog.objects.create(
                    family=family,
                    action=FamilyAuditLog.Action.FAMILY_STATUS_UPDATED,
                    target_type='Family',
                    target_id=str(family.id),
                    metadata={
                        'source': 'update_family_activity',
                        'is_idle': idle,
                        'season': season,
                        'since_week': since_week,
                    },
                )

        for label, families in (("idle", went_idle), ("active", came_back)):
            for family in families:
                logger.info("family %s (%s) -> %s", family.slug, family.id, label)
        self.stdout.write(
            f"{'[dry run] ' if dry_run else ''}season {season}: "
            f"{len(went_idle)} went idle, {len(came_back)} came back"
            + ("" if can_judge else " (fewer than 2 completed weeks; no new idle flags)")
        )
