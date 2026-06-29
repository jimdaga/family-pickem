from datetime import timedelta
import importlib

from django.apps import apps
from django.contrib import admin
from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone

from pickem_api.models import (
    Family, FamilyAuditLog, FamilyInvitation, FamilyMembership, Pool,
    PoolSettings,
    UserProfile, Teams, GamesAndScores, GamePicks,
    userSeasonPoints, userPoints, GameWeeks, userStats, currentSeason,
)
from pickem_api.serializers import (
    GameSerializer, currentSeasonSerializer, TeamsSerializer, GamePicksSerializer,
)
from pickem_api.authz import (
    AuthenticationRequired,
    PermissionDeniedForTenant,
    TenantNotFound,
    get_legacy_default_pool,
    require_family_membership,
    require_pool_membership,
    resolve_pool_context,
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


class TenantDomainAdminTest(TestCase):
    def test_tenant_domain_models_are_registered_in_admin(self):
        expected_models = [
            Family,
            FamilyMembership,
            Pool,
            PoolSettings,
            FamilyInvitation,
            FamilyAuditLog,
        ]

        for model in expected_models:
            self.assertIn(model, admin.site._registry)

    def test_invitation_admin_displays_hash_without_raw_code_fields(self):
        invitation_admin = admin.site._registry[FamilyInvitation]

        self.assertIn('code_hash', invitation_admin.list_display)
        self.assertNotIn('code', invitation_admin.list_display)
        self.assertNotIn('raw_code', invitation_admin.list_display)


class TenantAuthorizationHelperTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Smith Family', slug='smith-family')
        self.other_family = Family.objects.create(name='Jones Family', slug='jones-family')
        self.pool = Pool.objects.create(
            family=self.family,
            name='Main Pickem',
            slug='main',
            season=2526,
        )
        self.other_pool = Pool.objects.create(
            family=self.other_family,
            name='Main Pickem',
            slug='main',
            season=2526,
        )
        self.member = User.objects.create_user('member', email='member@example.com')
        self.admin_user = User.objects.create_user('admin-member', email='admin-member@example.com')
        self.owner = User.objects.create_user('owner-member', email='owner-member@example.com')
        self.inactive_user = User.objects.create_user('inactive-member', email='inactive@example.com')
        self.outsider = User.objects.create_user('outsider', email='outsider@example.com')
        self.superuser = User.objects.create_superuser('superuser', 'super@example.com', 'pass')
        self.commissioner = User.objects.create_user('commissioner', email='commissioner@example.com')
        UserProfile.objects.create(user=self.commissioner, is_commissioner=True)

        FamilyMembership.objects.create(
            family=self.family,
            user=self.member,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )
        FamilyMembership.objects.create(
            family=self.family,
            user=self.admin_user,
            role=FamilyMembership.Role.ADMIN,
            status=FamilyMembership.Status.ACTIVE,
        )
        FamilyMembership.objects.create(
            family=self.family,
            user=self.owner,
            role=FamilyMembership.Role.OWNER,
            status=FamilyMembership.Status.ACTIVE,
        )
        FamilyMembership.objects.create(
            family=self.family,
            user=self.inactive_user,
            role=FamilyMembership.Role.OWNER,
            status=FamilyMembership.Status.INACTIVE,
        )

    def test_active_member_can_resolve_family_membership(self):
        membership = require_family_membership(self.member, self.family)

        self.assertEqual(membership.user, self.member)
        self.assertEqual(membership.family, self.family)
        self.assertEqual(membership.role, FamilyMembership.Role.MEMBER)

    def test_role_hierarchy_allows_admin_and_owner_for_admin_requirement(self):
        admin_membership = require_family_membership(
            self.admin_user, self.family.slug, minimum_role=FamilyMembership.Role.ADMIN
        )
        owner_membership = require_family_membership(
            self.owner, self.family.id, minimum_role=FamilyMembership.Role.ADMIN
        )

        self.assertEqual(admin_membership.role, FamilyMembership.Role.ADMIN)
        self.assertEqual(owner_membership.role, FamilyMembership.Role.OWNER)

    def test_member_is_denied_for_admin_requirement(self):
        with self.assertRaises(PermissionDeniedForTenant):
            require_family_membership(
                self.member, self.family, minimum_role=FamilyMembership.Role.ADMIN
            )

    def test_inactive_and_outsider_memberships_are_not_found(self):
        with self.assertRaises(TenantNotFound):
            require_family_membership(self.inactive_user, self.family)

        with self.assertRaises(TenantNotFound):
            require_family_membership(self.outsider, self.family)

    def test_anonymous_requires_authentication(self):
        from django.contrib.auth.models import AnonymousUser

        with self.assertRaises(AuthenticationRequired):
            require_family_membership(AnonymousUser(), self.family)

    def test_superuser_and_legacy_commissioner_do_not_bypass_membership(self):
        with self.assertRaises(TenantNotFound):
            require_family_membership(self.superuser, self.family)

        with self.assertRaises(TenantNotFound):
            require_family_membership(self.commissioner, self.family)

    def test_pool_membership_requires_pool_to_belong_to_family(self):
        membership = require_pool_membership(
            self.member,
            pool=self.pool.slug,
            family=self.family.slug,
        )

        self.assertEqual(membership.family, self.family)

        with self.assertRaises(TenantNotFound):
            require_pool_membership(
                self.member,
                pool=self.other_pool,
                family=self.family.slug,
            )

    def test_family_member_cannot_resolve_other_family_pool(self):
        with self.assertRaises(TenantNotFound):
            require_pool_membership(
                self.member,
                pool=self.other_pool,
                family=self.other_family,
            )

    def test_legacy_default_pool_fallback_is_explicit(self):
        legacy_family, _ = Family.objects.get_or_create(
            slug='legacy-family-league',
            defaults={'name': 'Legacy Family League'},
        )
        legacy_pool, _ = Pool.objects.get_or_create(
            family=legacy_family,
            slug='2526-pickem',
            defaults={
                'name': '2025 Pickem',
                'season': 2526,
                'is_default': True,
            },
        )
        legacy_pool.is_default = True
        legacy_pool.save()

        self.assertEqual(get_legacy_default_pool(), legacy_pool)
        with self.assertRaises(TenantNotFound):
            resolve_pool_context(pool=None, family=None, allow_legacy_default=False)
        self.assertEqual(
            resolve_pool_context(pool=None, family=None, allow_legacy_default=True),
            legacy_pool,
        )

    def test_legacy_default_pool_uses_fallback_slug_when_no_default_pool_exists(self):
        legacy_family, _ = Family.objects.get_or_create(
            name='Legacy Family League',
            slug='legacy-family-league',
        )
        PoolSettings.objects.filter(pool__family=legacy_family).delete()
        Pool.objects.filter(family=legacy_family).delete()
        legacy_pool = Pool.objects.create(
            family=legacy_family,
            name='Legacy Pickem',
            slug='legacy-pickem',
            season=2024,
        )

        self.assertEqual(get_legacy_default_pool(), legacy_pool)


class LegacyPoolScopeModelTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Scope Test Family', slug='scope-test-family')
        self.pool = Pool.objects.create(
            family=self.family,
            name='2025 Pickem',
            slug='2526-pickem',
            season=2526,
        )

    def test_competition_models_have_nullable_pool_scope_without_strict_uniqueness(self):
        scoped_models = [GamePicks, userSeasonPoints, userPoints, userStats]

        for model in scoped_models:
            field = model._meta.get_field('pool')
            self.assertTrue(field.null, f'{model.__name__}.pool must stay nullable in Phase 1')
            self.assertTrue(field.blank, f'{model.__name__}.pool must allow blank admin/forms values')

        self.assertFalse(
            any(
                getattr(constraint, 'fields', None)
                and 'pool' in constraint.fields
                and model in scoped_models
                for model in scoped_models
                for constraint in model._meta.constraints
            ),
            'Phase 1 must not add strict pool-scoped uniqueness to legacy competition tables',
        )

    def test_competition_rows_accept_null_and_pool_without_changing_legacy_user_fields(self):
        null_pick = GamePicks.objects.create(
            id='nullable-pick',
            userEmail='legacy@example.com',
            uid=1001,
            userID='legacy-user',
            pick_game_id=1,
            pool=None,
        )
        scoped_pick = GamePicks.objects.create(
            id='scoped-pick',
            userEmail='legacy@example.com',
            uid=1001,
            userID='legacy-user',
            pick_game_id=2,
            pool=self.pool,
        )
        season_points = userSeasonPoints.objects.create(
            userEmail='legacy@example.com',
            userID='legacy-user',
            gameseason=2526,
            pool=self.pool,
        )
        retained_points = userPoints.objects.create(
            id='points-1',
            userEmail='legacy@example.com',
            userID='legacy-user',
            gameseason=2526,
            pool=self.pool,
        )
        stats = userStats.objects.create(
            userEmail='legacy@example.com',
            userID='legacy-user',
            pool=self.pool,
        )

        self.assertIsNone(null_pick.pool)
        self.assertEqual(scoped_pick.pool, self.pool)
        self.assertEqual(season_points.pool, self.pool)
        self.assertEqual(retained_points.pool, self.pool)
        self.assertEqual(stats.pool, self.pool)
        self.assertEqual(scoped_pick.userEmail, 'legacy@example.com')
        self.assertEqual(season_points.userID, 'legacy-user')
        self.assertEqual(retained_points.userID, 'legacy-user')
        self.assertEqual(stats.userEmail, 'legacy@example.com')


class LegacyPoolBackfillMigrationTest(TestCase):
    def setUp(self):
        FamilyMembership.objects.filter(family__slug='legacy-family-league').delete()
        PoolSettings.objects.filter(pool__family__slug='legacy-family-league').delete()
        Pool.objects.filter(family__slug='legacy-family-league').delete()
        Family.objects.filter(slug='legacy-family-league').delete()

    def _migration_module(self):
        return importlib.import_module('pickem_api.migrations.0074_add_legacy_pool_scope')

    def _run_backfill(self):
        self._migration_module().backfill_legacy_pool_scope(apps, None)

    def test_backfill_creates_legacy_pool_assigns_rows_and_preserves_roles_idempotently(self):
        currentSeason.objects.create(season=2526)
        owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='pass',
            is_superuser=True,
        )
        commissioner = User.objects.create_user(
            username='commissioner',
            email='commissioner@example.com',
            password='pass',
        )
        UserProfile.objects.create(user=commissioner, is_commissioner=True)
        member = User.objects.create_user(username='member', email='member@example.com', password='pass')
        admin_user = User.objects.create_user(username='admin', email='admin@example.com', password='pass')
        missing_reference = 'missing@example.com'

        family = Family.objects.create(name='Legacy Family League', slug='legacy-family-league')
        FamilyMembership.objects.create(
            family=family,
            user=admin_user,
            role=FamilyMembership.Role.ADMIN,
        )

        GamePicks.objects.create(id='pick-owner', uid=owner.id, userEmail=owner.email, userID=owner.username, pick_game_id=1)
        GamePicks.objects.create(id='pick-member', uid=member.id, userEmail=member.email, userID=member.username, pick_game_id=2)
        userSeasonPoints.objects.create(userEmail=commissioner.email, userID=commissioner.username, gameseason=2526)
        userPoints.objects.create(id='points-admin', userEmail=admin_user.email, userID=admin_user.username, gameseason=2526)
        userStats.objects.create(userEmail=missing_reference, userID='deleted-user')

        self._run_backfill()
        self._run_backfill()

        self.assertEqual(Family.objects.filter(slug='legacy-family-league').count(), 1)
        self.assertEqual(Pool.objects.filter(family=family).count(), 1)
        pool = Pool.objects.get(family=family)
        self.assertEqual(pool.slug, '2526-pickem')
        self.assertEqual(pool.season, 2526)
        self.assertTrue(PoolSettings.objects.filter(pool=pool).exists())
        self.assertFalse(GamePicks.objects.filter(pool__isnull=True).exists())
        self.assertFalse(userSeasonPoints.objects.filter(pool__isnull=True).exists())
        self.assertFalse(userPoints.objects.filter(pool__isnull=True).exists())
        self.assertFalse(userStats.objects.filter(pool__isnull=True).exists())

        self.assertEqual(
            FamilyMembership.objects.get(family=family, user=owner).role,
            FamilyMembership.Role.OWNER,
        )
        self.assertEqual(
            FamilyMembership.objects.get(family=family, user=commissioner).role,
            FamilyMembership.Role.ADMIN,
        )
        self.assertEqual(
            FamilyMembership.objects.get(family=family, user=member).role,
            FamilyMembership.Role.MEMBER,
        )
        self.assertEqual(
            FamilyMembership.objects.get(family=family, user=admin_user).role,
            FamilyMembership.Role.ADMIN,
        )
        self.assertEqual(FamilyMembership.objects.filter(family=family).count(), 4)

    def test_backfill_uses_active_commissioner_owner_fallback_when_no_active_superuser(self):
        inactive_superuser = User.objects.create_user(
            username='inactive-owner',
            email='inactive-owner@example.com',
            password='pass',
            is_superuser=True,
            is_active=False,
        )
        commissioner = User.objects.create_user(
            username='commissioner-owner',
            email='commissioner-owner@example.com',
            password='pass',
        )
        UserProfile.objects.create(user=commissioner, is_commissioner=True)
        GamePicks.objects.create(
            id='pick-inactive-superuser',
            uid=inactive_superuser.id,
            userEmail=inactive_superuser.email,
            userID=inactive_superuser.username,
            pick_game_id=1,
        )
        userSeasonPoints.objects.create(
            userEmail=commissioner.email,
            userID=commissioner.username,
        )

        self._run_backfill()

        family = Family.objects.get(slug='legacy-family-league')
        self.assertEqual(
            FamilyMembership.objects.get(family=family, user=commissioner).role,
            FamilyMembership.Role.OWNER,
        )
        self.assertFalse(FamilyMembership.objects.filter(family=family, user=inactive_superuser).exists())

    def test_backfill_uses_earliest_active_competition_or_message_board_user_owner_fallback(self):
        earliest_board_user = User.objects.create_user(
            username='earliest',
            email='earliest@example.com',
            password='pass',
        )
        later_competition_user = User.objects.create_user(
            username='later',
            email='later@example.com',
            password='pass',
        )
        GamePicks.objects.create(
            id='pick-later',
            uid=later_competition_user.id,
            userEmail=later_competition_user.email,
            userID=later_competition_user.username,
            pick_game_id=1,
        )
        from pickem_homepage.models import MessageBoardPost
        MessageBoardPost.objects.create(
            user=earliest_board_user,
            title='Legacy post',
            content='Legacy message board owner fallback source',
        )

        self._run_backfill()

        family = Family.objects.get(slug='legacy-family-league')
        self.assertEqual(
            FamilyMembership.objects.get(family=family, user=earliest_board_user).role,
            FamilyMembership.Role.OWNER,
        )
        self.assertEqual(
            FamilyMembership.objects.get(family=family, user=later_competition_user).role,
            FamilyMembership.Role.MEMBER,
        )


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
