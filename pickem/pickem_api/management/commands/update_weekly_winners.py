"""Award weekly winners for every active pool once the week is complete.

Runs from the update pipeline every minute, but only acts when all of the
week's games are finished and scored (i.e. after Monday Night Football),
and skips pools whose week is already awarded — so the award happens
exactly once, shortly after MNF goes final.
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from pickem.utils import get_season
from pickem_api.models import Family, Pool, WeekWinnerAnnouncement
from pickem_api.notifications import publish_week_winner_digest
from pickem_api.weekly_winners import (
    EspnGameStatsProvider,
    award_weekly_winners,
    complete_weeks,
    week_is_complete,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Award weekly winners for pools whose week has fully completed."

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, default=None)
        parser.add_argument(
            "--week", type=int, default=None,
            help="Week to award (defaults to the latest fully completed week).",
        )
        parser.add_argument(
            "--force", action="store_true",
            help="Re-award even if a winner is already flagged for the week.",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        week = options["week"]
        if week is None:
            # Walk every complete week, not just the latest: awarding is
            # idempotent per pool/week, and this back-fills any week whose
            # award was missed (e.g. a scheduler outage spanning MNF).
            weeks = complete_weeks(season)
            if not weeks:
                self.stdout.write("No completed week yet; nothing to award.")
                return
        elif not week_is_complete(season, week):
            self.stdout.write(
                f"Week {week} still has unfinished/unscored games; skipping."
            )
            return
        else:
            weeks = [week]

        stats_provider = EspnGameStatsProvider()
        # Skip pools of deactivated (soft-deleted) families — no bonuses are
        # awarded while a family is inactive — and other seasons' pools,
        # which could never award anything for this season anyway.
        pools = list(Pool.objects.filter(
            status=Pool.Status.ACTIVE,
            season=season,
            family__status=Family.Status.ACTIVE,
        ))
        awarded_by_week = {}
        for target_week in weeks:
            awarded = 0
            for pool in pools:
                try:
                    result = award_weekly_winners(
                        pool, season, target_week,
                        stats_provider=stats_provider,
                        force=options["force"],
                    )
                except Exception:
                    logger.exception(
                        "Weekly winner award failed for pool %s", pool
                    )
                    self.stderr.write(f" - {pool}: award failed (see logs)")
                    continue
                if result:
                    awarded += 1
                    self.stdout.write(
                        f" - {pool}: week {target_week} -> "
                        f"{', '.join(result['winners'])} "
                        f"(+{result['bonus_each']} each, via {result['method']})"
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Week {target_week}: awarded winners in {awarded} pool(s)."
                )
            )
            awarded_by_week[target_week] = awarded

        # Queue the newest week that *this pass* awarded for announcement, then
        # publish every queued week that hasn't gone out yet. The loop above
        # back-fills every missed award on purpose, but announcing is news, not
        # bookkeeping:
        #   - weeks awarded before this producer shipped (Weeks 1-2 of 2627)
        #     are never awarded again, so never queued: deploying is silent;
        #   - an outage that awards several weeks in one pass queues only the
        #     newest of them, not a digest per stale week;
        #   - a week awarded late on its own (a postponed game, or a tie held
        #     back for missing tiebreaker stats) is queued when it lands, even
        #     though a later week was announced first.
        # The queue is what makes a failed publish retryable: the award has
        # already committed, so without it the next tick would see nothing new
        # and the week's digests would be lost for good.
        awarded_weeks = [w for w in weeks if awarded_by_week.get(w)]  # ascending

        if options["force"]:
            # --force re-awards are corrections: rewrite digests that already
            # exist (so a changed winner is reflected), but never create or
            # queue new ones, so forcing an old week doesn't announce it.
            if awarded_weeks:
                self._publish(season, awarded_weeks[-1], pools, create_missing=False)
            return

        if awarded_weeks:
            WeekWinnerAnnouncement.objects.get_or_create(
                season=season, week=awarded_weeks[-1],
            )

        pending = WeekWinnerAnnouncement.objects.filter(
            season=season, published_at__isnull=True,
        ).order_by('week')
        for announcement in pending:
            if self._publish(season, announcement.week, pools):
                announcement.published_at = timezone.now()
                announcement.save(update_fields=['published_at'])

    def _publish(self, season, week, pools, create_missing=True):
        """Publish one week's digests; True on success, False if it failed.

        One digest per person after the whole week's pools are processed, not
        one per pool. A failure is logged and reported, never raised: the bonus
        points are the real work and are already committed.
        """
        try:
            sent = publish_week_winner_digest(
                season, week, pools, create_missing=create_missing,
            )
        except Exception:
            logger.exception(
                "Week winner notifications failed for season %s week %s",
                season, week,
            )
            self.stderr.write(
                f"Week {week}: winner notifications failed (see logs); "
                f"will retry next run"
            )
            return False
        if sent:
            self.stdout.write(
                f"Week {week}: sent or updated {sent} winner notification(s)."
            )
        return True
