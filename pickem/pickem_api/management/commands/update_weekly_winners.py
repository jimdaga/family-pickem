"""Award weekly winners for every active pool once the week is complete.

Runs from the update pipeline every minute, but only acts when all of the
week's games are finished and scored (i.e. after Monday Night Football),
and skips pools whose week is already awarded — so the award happens
exactly once, shortly after MNF goes final.
"""

import logging

from django.core.management.base import BaseCommand

from pickem.utils import get_season
from pickem_api.models import Family, Pool
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

        # Announce a week only when *this pass* awarded it, and only the latest
        # week. The loop above back-fills every missed award on purpose, but
        # announcing is news, not bookkeeping:
        #   - weeks awarded before this producer shipped (Weeks 1-2 of 2627)
        #     are never announced, so deploying mid-season is silent;
        #   - after a scheduler outage that awards several weeks in one pass,
        #     only the newest gets a digest, not one per stale week.
        # weeks is ascending (complete_weeks sorts it), so [-1] is the newest.
        #
        # Trade-off: if an award commits but publishing then fails, the next
        # tick sees the week as already awarded and does not retry, so that
        # week's digest is lost. The award itself is never affected.
        notify_week = weeks[-1]
        if not awarded_by_week.get(notify_week):
            return

        # One digest after the whole week's pools are processed, not one per
        # pool: a member of several families gets a single row naming them all.
        try:
            sent = publish_week_winner_digest(season, notify_week, pools)
        except Exception:
            # A notification failure must never roll back or mask an award: the
            # bonus points are the real work and are already committed.
            logger.exception(
                "Week winner notifications failed for season %s week %s",
                season, notify_week,
            )
            self.stderr.write(
                f"Week {notify_week}: winner notifications failed (see logs)"
            )
        else:
            if sent:
                self.stdout.write(
                    f"Week {notify_week}: sent {sent} winner notification(s)."
                )
