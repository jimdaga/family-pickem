"""Seed the isolated live-sim demo league PRE-kickoff (see demo_weekend.py).

Unlike seed_demo_week (which seeds finished games), this seeds a full ~13-game
weekend with games not-yet-started, ready for simulate_weekend to drive. All
data is keyed to DEMO_SLUG + DEMO_SEASON (9999); --wipe removes it. Dev-only.
"""
from datetime import timedelta

from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pickem_api.demo_weekend import (
    DEMO_POOL_SLUG, DEMO_SEASON, DEMO_SLUG, DEMO_WEEK, GAMES, PICKS,
    PLAYERS, TEAMS,
)
from pickem_api.models import (
    Family, FamilyAuditLog, FamilyMembership, GamePicks, GamesAndScores,
    Pool, PoolSettings, Teams, currentSeason, userPoints, userSeasonPoints,
    userStats,
)


class Command(BaseCommand):
    help = "Seed (or --wipe) the isolated live-sim demo weekend. Dev-only."

    def add_arguments(self, parser):
        parser.add_argument("--wipe", action="store_true")
        parser.add_argument("--owner", default=None,
                            help="Real username to add as OWNER so it's browsable.")
        parser.add_argument("--make-current", action="store_true",
                            help="Point the currentSeason singleton at 9999.")
        parser.add_argument("--print-current-season", action="store_true",
                            help="Print the current season int and exit.")

    def handle(self, *args, **options):
        if not django_settings.DEBUG:
            raise CommandError("seed_demo_weekend is a dev tool; DEBUG must be on.")

        if options["print_current_season"]:
            row = currentSeason.objects.first()
            self.stdout.write(str(row.season if row else ""))
            return
        if options["make_current"]:
            row = currentSeason.objects.first()
            if row is None:
                row = currentSeason.objects.create(season=DEMO_SEASON)
            else:
                row.season = DEMO_SEASON
                row.save(update_fields=["season"])
            self.stdout.write(self.style.SUCCESS(
                f"currentSeason set to {DEMO_SEASON}."))
            return
        if options["wipe"]:
            self._wipe()
            return

        family, _ = Family.objects.get_or_create(
            slug=DEMO_SLUG,
            defaults={"name": "Demo Live Sim", "status": Family.Status.ACTIVE})
        pool, _ = Pool.objects.get_or_create(
            family=family, slug=DEMO_POOL_SLUG,
            defaults={"name": "Demo Pool", "season": DEMO_SEASON,
                      "competition": "nfl", "status": Pool.Status.ACTIVE,
                      "is_default": True})
        PoolSettings.objects.get_or_create(pool=pool)

        users = {}
        for i, username in enumerate(PLAYERS):
            user, _ = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"})
            users[username] = user
            FamilyMembership.objects.get_or_create(
                family=family, user=user,
                defaults={"role": FamilyMembership.Role.MEMBER,
                          "status": FamilyMembership.Status.ACTIVE})
            # UserProfile: only set fields confirmed to exist (see note above).
            self._ensure_profile(user, TEAMS[i % len(TEAMS)][1])

        owner_username = options.get("owner")
        if owner_username:
            owner = User.objects.filter(username=owner_username).first()
            if owner is None:
                raise CommandError(f"--owner user '{owner_username}' not found.")
            FamilyMembership.objects.get_or_create(
                family=family, user=owner,
                defaults={"role": FamilyMembership.Role.OWNER,
                          "status": FamilyMembership.Status.ACTIVE})

        for team_id, slug, name, color in TEAMS:
            Teams.objects.update_or_create(id=team_id, defaults=dict(
                gameseason=DEMO_SEASON, teamNameSlug=slug, teamNameName=name,
                teamLogo="/static/images/nfl.svg", teamWins=0, teamLosses=0,
                teamTies=0, color=color, alternateColor="334155"))

        base = timezone.now()
        for g in GAMES:
            # Kickoff timestamps spread so the scores page ordering looks real.
            kickoff = base + timedelta(hours=g["kickoff_frac"] * 72)
            GamesAndScores.objects.update_or_create(id=g["id"], defaults={
                "slug": f'{g["home"]}-{g["away"]}', "competition": "nfl",
                "gameWeek": DEMO_WEEK, "gameyear": "2099",
                "gameseason": DEMO_SEASON, "startTimestamp": kickoff,
                "statusType": "notstarted", "statusTitle": "Scheduled",
                "gameWinner": "", "gameScored": False,
                "tieBreakerGame": g["tiebreaker"],
                "homeTeamId": g["id"] * 10 + 1, "homeTeamSlug": g["home"],
                "homeTeamName": g["home_name"], "homeTeamScore": 0,
                "awayTeamId": g["id"] * 10 + 2, "awayTeamSlug": g["away"],
                "awayTeamName": g["away_name"], "awayTeamScore": 0})

        games_by_id = {g["id"]: g for g in GAMES}
        pick_count = 0
        for username, cfg in PICKS.items():
            user = users[username]
            for game_id, pick in cfg["picks"].items():
                g = games_by_id[game_id]
                GamePicks.objects.update_or_create(
                    id=f"{pool.id}-{user.id}-{game_id}", defaults={
                        "pool": pool, "pick_game_id": game_id,
                        "slug": f'{g["home"]}-{g["away"]}', "userID": str(user.id),
                        "uid": user.id, "userEmail": user.email,
                        "gameWeek": DEMO_WEEK, "gameyear": "2099",
                        "gameseason": DEMO_SEASON, "competition": "nfl",
                        "pick": pick, "pick_correct": False,
                        "tieBreakerScore": cfg["tb_score"] if g["tiebreaker"] else None,
                        "tieBreakerYards": cfg["tb_yards"] if g["tiebreaker"] else None})
                pick_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded '{family.name}' (season {DEMO_SEASON}): {len(users)} players, "
            f"{len(GAMES)} pre-kickoff games, {pick_count} picks. "
            f"Run simulate_weekend to drive it."))

    def _ensure_profile(self, user, favorite_team_slug):
        """Best-effort UserProfile with a favorite team + tagline. Kept
        defensive so a schema drift can't break seeding."""
        try:
            from pickem_api.models import UserProfile
        except Exception:
            return
        UserProfile.objects.get_or_create(
            user=user, defaults={
                "tagline": "Demo player",
                "favorite_team": favorite_team_slug,
            })

    def _wipe(self):
        family = Family.objects.filter(slug=DEMO_SLUG).first()
        GamePicks.objects.filter(gameseason=DEMO_SEASON).delete()
        userSeasonPoints.objects.filter(gameseason=DEMO_SEASON).delete()
        GamesAndScores.objects.filter(gameseason=DEMO_SEASON).delete()
        Teams.objects.filter(gameseason=DEMO_SEASON).delete()
        if family:
            FamilyAuditLog.objects.filter(family=family).delete()
            FamilyMembership.objects.filter(family=family).delete()
            for pool in family.pools.all():
                GamePicks.objects.filter(pool=pool).delete()
                userSeasonPoints.objects.filter(pool=pool).delete()
                userPoints.objects.filter(pool=pool).delete()
                userStats.objects.filter(pool=pool).delete()
                PoolSettings.objects.filter(pool=pool).delete()
                pool.delete()
            family.delete()
        User.objects.filter(username__in=PLAYERS).delete()
        self.stdout.write(self.style.SUCCESS("Demo live-sim data wiped."))
