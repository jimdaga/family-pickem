from datetime import timedelta

from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone

from pickem_api.models import (
    Family, FamilyAuditLog, FamilyInvitation, FamilyMembership, Pool,
    PoolSettings,
    UserProfile, Teams, GamesAndScores, GamePicks,
    userSeasonPoints, GameWeeks, userStats, currentSeason,
)
from pickem_api.serializers import (
    GameSerializer, currentSeasonSerializer, TeamsSerializer, GamePicksSerializer,
)


class UserProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_create_profile(self):
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(profile.user, self.user)

    def test_str(self):
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(str(profile), "testuser's Profile")

    def test_defaults(self):
        profile = UserProfile.objects.create(user=self.user)
        self.assertTrue(profile.email_notifications)
        self.assertFalse(profile.dark_mode)
        self.assertFalse(profile.private_profile)
        self.assertFalse(profile.is_commissioner)


class TenantDomainModelTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner', email='owner@example.com', password='pass'
        )

    def test_family_slug_is_unique_and_string_is_readable(self):
        family = Family.objects.create(name='Smith Family', slug='smith-family')

        self.assertEqual(str(family), 'Smith Family')
        with self.assertRaises(IntegrityError):
            Family.objects.create(name='Other Smiths', slug='smith-family')

    def test_pool_slug_is_unique_per_family_only(self):
        family = Family.objects.create(name='Smith Family', slug='smith-family')
        other_family = Family.objects.create(name='Jones Family', slug='jones-family')
        pool = Pool.objects.create(
            family=family,
            name='Main Pickem',
            slug='main',
            season=2526,
        )

        self.assertEqual(str(pool), 'Smith Family - Main Pickem')
        Pool.objects.create(
            family=family,
            name='Side Pool',
            slug='side',
            season=2526,
        )
        Pool.objects.create(
            family=other_family,
            name='Main Pickem',
            slug='main',
            season=2526,
        )
        with self.assertRaises(IntegrityError):
            Pool.objects.create(
                family=family,
                name='Duplicate Main',
                slug='main',
                season=2526,
            )

    def test_membership_allows_user_in_multiple_families_and_rejects_duplicate_family_user(self):
        family = Family.objects.create(name='Smith Family', slug='smith-family')
        other_family = Family.objects.create(name='Jones Family', slug='jones-family')

        owner_membership = FamilyMembership.objects.create(
            family=family,
            user=self.owner,
            role=FamilyMembership.Role.OWNER,
            status=FamilyMembership.Status.ACTIVE,
        )
        other_membership = FamilyMembership.objects.create(
            family=other_family,
            user=self.owner,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.INACTIVE,
        )

        self.assertEqual(owner_membership.role, FamilyMembership.Role.OWNER)
        self.assertEqual(other_membership.status, FamilyMembership.Status.INACTIVE)
        self.assertIn(FamilyMembership.Role.ADMIN, dict(FamilyMembership.Role.choices))
        with self.assertRaises(IntegrityError):
            FamilyMembership.objects.create(
                family=family,
                user=self.owner,
                role=FamilyMembership.Role.ADMIN,
            )

    def test_pool_settings_are_one_to_one_with_pool(self):
        family = Family.objects.create(name='Smith Family', slug='smith-family')
        pool = Pool.objects.create(
            family=family,
            name='Main Pickem',
            slug='main',
            season=2526,
        )

        settings = PoolSettings.objects.create(pool=pool)

        self.assertEqual(settings.pool, pool)
        with self.assertRaises(IntegrityError):
            PoolSettings.objects.create(pool=pool)

    def test_family_invitation_stores_hash_only_and_lifecycle_fields(self):
        family = Family.objects.create(name='Smith Family', slug='smith-family')
        pool = Pool.objects.create(
            family=family,
            name='Main Pickem',
            slug='main',
            season=2526,
        )
        invitation = FamilyInvitation.objects.create(
            family=family,
            pool=pool,
            code_hash='sha256:invite-hash',
            role=FamilyMembership.Role.MEMBER,
            expires_at=timezone.now() + timedelta(days=7),
            max_uses=3,
            created_by=self.owner,
        )

        self.assertEqual(invitation.code_hash, 'sha256:invite-hash')
        self.assertFalse(invitation.is_revoked)
        self.assertEqual(invitation.use_count, 0)
        self.assertFalse(hasattr(invitation, 'code'))
        self.assertFalse(hasattr(invitation, 'raw_code'))

    def test_family_audit_log_records_sensitive_action_metadata(self):
        family = Family.objects.create(name='Smith Family', slug='smith-family')
        pool = Pool.objects.create(
            family=family,
            name='Main Pickem',
            slug='main',
            season=2526,
        )

        audit = FamilyAuditLog.objects.create(
            family=family,
            pool=pool,
            actor=self.owner,
            action=FamilyAuditLog.Action.INVITATION_CREATED,
            target_type='FamilyInvitation',
            target_id='invite-1',
            metadata={'role': FamilyMembership.Role.MEMBER},
            ip_address='127.0.0.1',
            user_agent='Django test client',
        )

        self.assertEqual(audit.family, family)
        self.assertEqual(audit.pool, pool)
        self.assertEqual(audit.actor, self.owner)
        self.assertEqual(audit.metadata['role'], FamilyMembership.Role.MEMBER)
        self.assertIsNotNone(audit.created_at)


class TeamsModelTest(TestCase):
    def test_create_team(self):
        team = Teams.objects.create(
            id=1, teamNameSlug='eagles', teamNameName='Philadelphia Eagles',
        )
        self.assertEqual(team.teamNameSlug, 'eagles')
        self.assertEqual(team.teamWins, 0)
        self.assertEqual(team.teamLosses, 0)
        self.assertEqual(team.teamTies, 0)


class GamesAndScoresModelTest(TestCase):
    def test_create_game(self):
        game = GamesAndScores.objects.create(
            id=100,
            slug='eagles-chiefs',
            competition='nfl',
            gameWeek='1',
            gameyear='2025',
            startTimestamp=timezone.now(),
            statusType='pre',
            statusTitle='Scheduled',
            homeTeamId=1,
            homeTeamSlug='eagles',
            homeTeamName='Philadelphia Eagles',
            awayTeamId=2,
            awayTeamSlug='chiefs',
            awayTeamName='Kansas City Chiefs',
        )
        self.assertEqual(game.slug, 'eagles-chiefs')
        self.assertFalse(game.tieBreakerGame)
        self.assertFalse(game.gameScored)


class GamePicksModelTest(TestCase):
    def test_create_pick(self):
        pick = GamePicks.objects.create(
            id='pick-1', pick_game_id=100,
        )
        self.assertEqual(pick.id, 'pick-1')
        self.assertFalse(pick.pick_correct)


class UserSeasonPointsModelTest(TestCase):
    def test_create_season_points(self):
        sp = userSeasonPoints.objects.create()
        self.assertIsNotNone(sp.id)
        self.assertIsNone(sp.total_points)
        self.assertFalse(sp.year_winner)


class GameWeeksModelTest(TestCase):
    def test_create_gameweek(self):
        gw = GameWeeks.objects.create(
            weekNumber=1, competition='nfl', date='2025-09-04',
        )
        self.assertEqual(gw.weekNumber, 1)


class UserStatsModelTest(TestCase):
    def test_create_stats(self):
        stat = userStats.objects.create()
        self.assertIsNotNone(stat.id)


class CurrentSeasonModelTest(TestCase):
    def test_str_with_display_name(self):
        cs = currentSeason.objects.create(season=2526, display_name='2025-2026')
        self.assertEqual(str(cs), '2025-2026')

    def test_str_without_display_name(self):
        cs = currentSeason.objects.create(season=2526)
        self.assertEqual(str(cs), '2526')

    def test_get_display_season_with_display_name(self):
        cs = currentSeason.objects.create(season=2526, display_name='2025-2026')
        self.assertEqual(cs.get_display_season(), '2025-2026')

    def test_get_display_season_formats_season_number(self):
        cs = currentSeason.objects.create(season=2526)
        self.assertEqual(cs.get_display_season(), '2025-2026')

    def test_get_display_season_none(self):
        cs = currentSeason.objects.create()
        self.assertEqual(cs.get_display_season(), 'None')


class GameSerializerTest(TestCase):
    def test_valid_data(self):
        now = timezone.now()
        game = GamesAndScores.objects.create(
            id=200,
            slug='bears-packers',
            competition='nfl',
            gameWeek='2',
            gameyear='2025',
            startTimestamp=now,
            statusType='pre',
            statusTitle='Scheduled',
            homeTeamId=3,
            homeTeamSlug='bears',
            homeTeamName='Chicago Bears',
            awayTeamId=4,
            awayTeamSlug='packers',
            awayTeamName='Green Bay Packers',
        )
        serializer = GameSerializer(game)
        data = serializer.data
        self.assertEqual(data['id'], 200)
        self.assertEqual(data['slug'], 'bears-packers')
        self.assertEqual(data['homeTeamName'], 'Chicago Bears')
        self.assertEqual(data['awayTeamName'], 'Green Bay Packers')


class CurrentSeasonSerializerTest(TestCase):
    def test_valid_data(self):
        cs = currentSeason.objects.create(season=2526, display_name='2025-2026')
        serializer = currentSeasonSerializer(cs)
        data = serializer.data
        self.assertEqual(data['season'], 2526)
        self.assertEqual(data['display_name'], '2025-2026')


class TeamsSerializerTest(TestCase):
    def test_valid_data(self):
        team = Teams.objects.create(
            id=10, teamNameSlug='ravens', teamNameName='Baltimore Ravens',
        )
        serializer = TeamsSerializer(team)
        data = serializer.data
        self.assertEqual(data['id'], 10)
        self.assertEqual(data['teamNameSlug'], 'ravens')
        self.assertEqual(data['teamNameName'], 'Baltimore Ravens')
        self.assertEqual(data['teamWins'], 0)


class GamePicksSerializerTest(TestCase):
    def test_valid_data(self):
        pick = GamePicks.objects.create(
            id='pick-ser-1', pick_game_id=300, userID='user1',
            gameWeek='3', gameyear='2025', pick='eagles',
        )
        serializer = GamePicksSerializer(pick)
        data = serializer.data
        self.assertEqual(data['id'], 'pick-ser-1')
        self.assertEqual(data['pick_game_id'], 300)
        self.assertEqual(data['pick'], 'eagles')
        self.assertNotIn('userEmail', data)
