"""Seed an isolated demo league to exercise the full update pipeline.

Creates a synthetic family/pool in fake season 9999 with four members, a
completed week of three games (the last one flagged as the MNF tiebreaker),
and picks crafted so two players tie at the top and the tiebreaker must
resolve it. Everything is keyed to the demo slug + season 9999, so it can't
collide with real data, and --wipe removes it all.

Intended flow (all season-scoped, so the live scheduler is unaffected):

    manage.py seed_demo_week
    manage.py update_picks --season 9999
    manage.py update_standings --season 9999
    manage.py update_weekly_winners --season 9999
    manage.py update_rankings --season 9999

Dev-only: refuses to run unless DEBUG is on.
"""

from datetime import timedelta

from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pickem_api.models import (
    Family,
    FamilyAuditLog,
    FamilyMembership,
    GamePicks,
    GamesAndScores,
    Pool,
    PoolSettings,
    Teams,
    userSeasonPoints,
)

DEMO_SLUG = 'demo-engine-test'
DEMO_SEASON = 9999
GAME_IDS = [9999901, 9999902, 9999903]

# (game id, home slug/name, away slug/name, home score, away score, winner, is MNF)
GAMES = [
    (9999901, 'demo-sharks', 'Demo Sharks', 'demo-eagles', 'Demo Eagles', 27, 13, 'demo-sharks', False),
    (9999902, 'demo-colts', 'Demo Colts', 'demo-bears', 'Demo Bears', 10, 31, 'demo-bears', False),
    (9999903, 'demo-lions', 'Demo Lions', 'demo-tigers', 'Demo Tigers', 24, 20, 'demo-lions', True),
]

# username -> {game id: pick}, plus tiebreaker predictions on the MNF game.
# alice and bob tie at 2 correct; alice's total-score guess is closer
# (41 vs 50, actual 44) so the primary tiebreaker resolves it.
PICKS = {
    'demo-alice': {
        'picks': {9999901: 'demo-sharks', 9999902: 'demo-bears', 9999903: 'demo-tigers'},
        'tb_score': 41, 'tb_yards': 650,
    },
    'demo-bob': {
        'picks': {9999901: 'demo-sharks', 9999902: 'demo-bears', 9999903: 'demo-tigers'},
        'tb_score': 50, 'tb_yards': 800,
    },
    'demo-carol': {
        'picks': {9999901: 'demo-sharks', 9999902: 'demo-colts', 9999903: 'demo-tigers'},
        'tb_score': 44, 'tb_yards': 700,
    },
    'demo-dave': {  # missed game 2 entirely
        'picks': {9999901: 'demo-eagles', 9999903: 'demo-tigers'},
        'tb_score': None, 'tb_yards': None,
    },
}


class Command(BaseCommand):
    help = "Seed (or --wipe) an isolated demo league for pipeline testing."

    def add_arguments(self, parser):
        parser.add_argument('--wipe', action='store_true', help='Remove all demo data.')
        parser.add_argument(
            '--owner', default=None,
            help='Optionally add this real username as an owner of the demo family '
                 'so it is browsable in the UI.',
        )

    def handle(self, *args, **options):
        if not django_settings.DEBUG:
            raise CommandError('seed_demo_week is a dev tool; DEBUG must be on.')

        if options['wipe']:
            self._wipe()
            return

        family, _ = Family.objects.get_or_create(
            slug=DEMO_SLUG,
            defaults={'name': 'Demo Engine Test', 'status': Family.Status.ACTIVE},
        )
        pool, _ = Pool.objects.get_or_create(
            family=family,
            slug='demo-pool',
            defaults={
                'name': 'Demo Pool',
                'season': DEMO_SEASON,
                'competition': 'nfl',
                'status': Pool.Status.ACTIVE,
                'is_default': True,
            },
        )
        PoolSettings.objects.get_or_create(pool=pool)

        users = {}
        for username in PICKS:
            user, _ = User.objects.get_or_create(
                username=username, defaults={'email': f'{username}@example.com'}
            )
            users[username] = user
            FamilyMembership.objects.get_or_create(
                family=family, user=user,
                defaults={
                    'role': FamilyMembership.Role.MEMBER,
                    'status': FamilyMembership.Status.ACTIVE,
                },
            )

        # Optionally add one real account so the demo league is browsable in
        # the UI. Explicit opt-in only: auto-adding real users makes the demo
        # family look like cross-tenant contamination.
        owner_username = options.get('owner')
        if owner_username:
            owner = User.objects.filter(username=owner_username).first()
            if owner is None:
                raise CommandError(f"--owner user '{owner_username}' not found.")
            FamilyMembership.objects.get_or_create(
                family=family, user=owner,
                defaults={
                    'role': FamilyMembership.Role.OWNER,
                    'status': FamilyMembership.Status.ACTIVE,
                },
            )

        # Teams rows so pick/score cards can render logos and colors.
        demo_teams = [
            (999911, 'demo-sharks', 'Demo Sharks', '0ea5e9'),
            (999912, 'demo-eagles', 'Demo Eagles', '16a34a'),
            (999913, 'demo-colts', 'Demo Colts', '2563eb'),
            (999914, 'demo-bears', 'Demo Bears', 'ea580c'),
            (999915, 'demo-lions', 'Demo Lions', 'ca8a04'),
            (999916, 'demo-tigers', 'Demo Tigers', 'dc2626'),
        ]
        for team_id, slug, name, color in demo_teams:
            Teams.objects.update_or_create(id=team_id, defaults=dict(
                gameseason=DEMO_SEASON, teamNameSlug=slug, teamNameName=name,
                teamLogo='/static/images/nfl.svg', teamWins=0, teamLosses=0,
                teamTies=0, color=color, alternateColor='334155'))

        kickoff = timezone.now() - timedelta(days=2)
        for game_id, home, home_name, away, away_name, hs, as_, winner, is_mnf in GAMES:
            GamesAndScores.objects.update_or_create(
                id=game_id,
                defaults={
                    'slug': f'{home}-{away}',
                    'competition': 'nfl',
                    'gameWeek': '1',
                    'gameyear': '2099',
                    'gameseason': DEMO_SEASON,
                    'startTimestamp': kickoff + timedelta(hours=GAME_IDS.index(game_id) * 8),
                    'statusType': 'finished',
                    'statusTitle': 'Final',
                    'gameWinner': winner,
                    'gameScored': False,  # let update_picks do the real scoring
                    'tieBreakerGame': is_mnf,
                    'homeTeamId': game_id * 10 + 1,
                    'homeTeamSlug': home,
                    'homeTeamName': home_name,
                    'homeTeamScore': hs,
                    'awayTeamId': game_id * 10 + 2,
                    'awayTeamSlug': away,
                    'awayTeamName': away_name,
                    'awayTeamScore': as_,
                },
            )

        pick_count = 0
        for username, config in PICKS.items():
            user = users[username]
            for game_id, pick in config['picks'].items():
                game = GamesAndScores.objects.get(id=game_id)
                GamePicks.objects.update_or_create(
                    id=f'{pool.id}-{user.id}-{game_id}',
                    defaults={
                        'pool': pool,
                        'pick_game_id': game_id,
                        'slug': game.slug,
                        'userID': str(user.id),
                        'uid': user.id,
                        'userEmail': user.email,
                        'gameWeek': '1',
                        'gameyear': '2099',
                        'gameseason': DEMO_SEASON,
                        'competition': 'nfl',
                        'pick': pick,
                        'pick_correct': False,  # update_picks will grade
                        'tieBreakerScore': config['tb_score'] if game.tieBreakerGame else None,
                        'tieBreakerYards': config['tb_yards'] if game.tieBreakerGame else None,
                    },
                )
                pick_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded demo league '{family.name}' (season {DEMO_SEASON}): "
            f"{len(users)} players, {len(GAMES)} finished games, {pick_count} picks.\n"
            f"Expected outcome: alice & bob tie at 2 correct; alice wins the "
            f"total-score tiebreaker (41 vs 50, actual 44) and gets the bonus."
        ))

    def _wipe(self):
        family = Family.objects.filter(slug=DEMO_SLUG).first()
        deleted = {
            'picks': GamePicks.objects.filter(gameseason=DEMO_SEASON).delete()[0],
            'standings': userSeasonPoints.objects.filter(gameseason=DEMO_SEASON).delete()[0],
            'games': GamesAndScores.objects.filter(gameseason=DEMO_SEASON).delete()[0],
            'teams': Teams.objects.filter(gameseason=DEMO_SEASON).delete()[0],
        }
        if family:
            deleted['audit'] = FamilyAuditLog.objects.filter(family=family).delete()[0]
            deleted['memberships'] = FamilyMembership.objects.filter(family=family).delete()[0]
            for pool in family.pools.all():
                PoolSettings.objects.filter(pool=pool).delete()
                pool.delete()
            family.delete()
        deleted['users'] = User.objects.filter(username__startswith='demo-').delete()[0]
        self.stdout.write(self.style.SUCCESS(f'Demo data wiped: {deleted}'))
