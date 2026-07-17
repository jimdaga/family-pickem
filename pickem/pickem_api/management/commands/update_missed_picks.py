"""Apply each pool's missed-pick policy once games lock.

For pools configured with ``missed_pick_policy`` of ``auto_home`` or
``auto_favorite``, every active member who hasn't submitted a pick for a
started (locked) game gets one generated automatically — the home team, or
the betting favorite (falling back to the home team when no odds are
available). Pools on ``zero_points`` (the default) are untouched.

Generated picks are flagged ``auto_pick=True`` so downstream consumers can
tell them apart: ``update_picks``/``update_standings`` score them like any
other pick (that's the point of the policy), while ``update_stats`` still
counts the game as missed and excludes it from accuracy and perfect weeks.

A game only qualifies once it has started (``startTimestamp`` in the past)
and hasn't been scored yet — under both locking modes a started game can no
longer be picked by the user, and ``update_picks`` only grades unscored
games, so the auto pick always lands in time to be scored. Games scored
before this job saw them are left alone (no retroactive picks).

Runs from the update pipeline between ``update_games`` and ``update_picks``.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from pickem.utils import get_season
from pickem_api.models import (
    Family,
    FamilyMembership,
    GamePicks,
    GamesAndScores,
    Pool,
    PoolSettings,
)

logger = logging.getLogger(__name__)


def favorite_slug(game):
    """The betting favorite's slug, falling back to the home team.

    Win probabilities are derived from ESPN's favorite flag + spread in
    update_games, so comparing them identifies the favorite; a pick'em
    (equal/missing probabilities) defaults to home.
    """
    home = game.homeTeamWinProbability
    away = game.awayTeamWinProbability
    if home is not None and away is not None and away > home:
        return game.awayTeamSlug
    return game.homeTeamSlug


class Command(BaseCommand):
    help = "Create policy-driven auto picks for members who missed locked games."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="Season in YYZZ format (defaults to the current season).",
        )

    def handle(self, *args, **options):
        season = options["season"] or get_season()
        now = timezone.now()
        User = get_user_model()

        # Deactivated (soft-deleted) families must not keep accruing auto
        # picks — their members can't play, so a generated pick would just
        # poison the data for a later reactivation.
        pools = Pool.objects.filter(
            status=Pool.Status.ACTIVE,
            season=season,
            family__status=Family.Status.ACTIVE,
        ).select_related("family")

        created_total = 0
        for pool in pools:
            settings = PoolSettings.objects.filter(pool=pool).first()
            if not settings or settings.missed_pick_policy == (
                PoolSettings.MissedPickPolicy.ZERO_POINTS
            ):
                continue

            games = list(
                GamesAndScores.objects.filter(
                    gameseason=pool.season,
                    competition=pool.competition,
                    gameScored=False,
                    startTimestamp__lte=now,
                )
            )
            if not games:
                continue

            member_ids = list(
                FamilyMembership.objects.filter(
                    family=pool.family,
                    status=FamilyMembership.Status.ACTIVE,
                    user__is_active=True,
                ).values_list("user_id", flat=True)
            )
            if not member_ids:
                continue
            users = {
                user.id: user
                for user in User.objects.filter(id__in=member_ids)
            }

            existing = set(
                GamePicks.objects.filter(
                    pool=pool,
                    pick_game_id__in=[game.id for game in games],
                ).values_list("userID", "pick_game_id")
            )

            to_create = []
            for game in games:
                if settings.missed_pick_policy == PoolSettings.MissedPickPolicy.AUTO_HOME:
                    pick_slug = game.homeTeamSlug
                else:  # AUTO_FAVORITE
                    pick_slug = favorite_slug(game)
                for user_id in member_ids:
                    if (str(user_id), game.id) in existing:
                        continue
                    user = users.get(user_id)
                    if user is None:
                        continue
                    to_create.append(
                        GamePicks(
                            id=f"{pool.id}-{user.id}-{game.id}",
                            pool=pool,
                            userEmail=user.email,
                            userID=str(user.id),
                            uid=user.id,
                            slug=game.slug,
                            competition=game.competition,
                            gameWeek=game.gameWeek,
                            gameyear=game.gameyear,
                            gameseason=game.gameseason,
                            pick_game_id=game.id,
                            pick=pick_slug,
                            pick_correct=False,
                            auto_pick=True,
                        )
                    )

            if to_create:
                # ignore_conflicts guards against a pick submitted between the
                # existence check and the insert (locking is time-based, so a
                # request racing the pipeline is possible around kickoff).
                created = len(
                    GamePicks.objects.bulk_create(to_create, ignore_conflicts=True)
                )
                created_total += created
                self.stdout.write(
                    f" - {pool.family.slug}/{pool.slug}: "
                    f"{created} auto pick(s) ({settings.missed_pick_policy})"
                )

        self.stdout.write(
            self.style.SUCCESS(f"Created {created_total} auto pick(s).")
        )
