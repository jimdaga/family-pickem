from datetime import date, timedelta
import importlib
from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.contrib import admin
from django.core.management.base import CommandError
from django.test import Client
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
            recipient_email='joiner@example.com',
            role=FamilyMembership.Role.MEMBER,
            expires_at=timezone.now() + timedelta(days=7),
            max_uses=3,
            created_by=self.owner,
        )

        self.assertEqual(invitation.code_hash, 'sha256:invite-hash')
        self.assertEqual(invitation.recipient_email, 'joiner@example.com')
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

        self.assertIn('recipient_email', invitation_admin.list_display)
        self.assertIn('code_hash', invitation_admin.list_display)
        self.assertNotIn('code', invitation_admin.list_display)
        self.assertNotIn('raw_code', invitation_admin.list_display)

    def test_teams_admin_displays_logo_contrast_preset(self):
        teams_admin = admin.site._registry[Teams]
        teams_form = teams_admin.get_form(None)

        self.assertIn('logo_contrast_preset', teams_admin.list_display)
        self.assertIn('logo_contrast_preset', teams_form.base_fields)


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

    def test_superuser_gets_god_mode_but_commissioner_stays_family_scoped(self):
        # Superusers are site operators (like SREs): they may observe and
        # administer every family via a synthetic, never-persisted owner
        # membership.
        membership = require_family_membership(self.superuser, self.family)
        self.assertEqual(membership.role, FamilyMembership.Role.OWNER)
        self.assertIsNone(membership.pk)  # synthetic — never saved
        self.assertFalse(
            FamilyMembership.objects.filter(user=self.superuser).exists()
        )

        # A commissioner governs a single family only — the profile flag
        # grants nothing outside their own memberships.
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


class TenantAuthorizationApiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.family = Family.objects.create(name='Smith Family', slug='smith-family')
        self.other_family = Family.objects.create(name='Jones Family', slug='jones-family')
        self.pool = Pool.objects.create(
            family=self.family,
            name='Main Pickem',
            slug='main',
            season=2526,
        )
        self.member = User.objects.create_user('member', email='member@example.com', password='pass')
        self.admin_user = User.objects.create_user('admin-member', email='admin@example.com', password='pass')
        self.owner = User.objects.create_user('owner-member', email='owner@example.com', password='pass')
        self.outsider = User.objects.create_user('outsider', email='outsider@example.com', password='pass')

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

    def _url(self, family_slug='smith-family', pool_slug='main'):
        return f'/api/families/{family_slug}/pools/{pool_slug}/authz-check/'

    def test_api_authz_check_requires_authentication(self):
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['detail'], 'Authentication required.')

    def test_api_authz_check_returns_404_for_non_member(self):
        self.client.force_login(self.outsider)

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['detail'], 'Not found.')

    def test_api_authz_check_returns_member_context_for_member(self):
        self.client.force_login(self.member)

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                'family': 'smith-family',
                'pool': 'main',
                'role': FamilyMembership.Role.MEMBER,
            },
        )

    def test_api_authz_check_returns_403_for_wrong_role(self):
        self.client.force_login(self.member)

        response = self.client.get(self._url() + '?minimum_role=admin')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['detail'], 'Permission denied.')

    def test_api_authz_check_allows_admin_and_owner_for_admin_role(self):
        for user in [self.admin_user, self.owner]:
            self.client.force_login(user)
            response = self.client.get(self._url() + '?minimum_role=admin')

            self.assertEqual(response.status_code, 200)

    def test_api_authz_check_returns_404_for_pool_family_mismatch(self):
        Pool.objects.create(
            family=self.other_family,
            name='Other Main',
            slug='other-main',
            season=2526,
        )
        self.client.force_login(self.member)

        response = self.client.get(self._url(pool_slug='other-main'))

        self.assertEqual(response.status_code, 404)


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

    def test_logo_contrast_preset_defaults_to_model_default(self):
        team = Teams.objects.create(
            id=2,
            teamNameSlug='chiefs',
            teamNameName='Kansas City Chiefs',
        )

        self.assertEqual(
            team.logo_contrast_preset,
            Teams.LogoContrastPreset.DEFAULT,
        )


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


class UpdateRecordsCommandTest(TestCase):
    """ORM-based `update_records` management command (replaces cron_update_records.py)."""

    SAMPLE_TEAM = {
        "id": "17",
        "slug": "new-england-patriots",
        "displayName": "New England Patriots",
        "color": "002244",
        "alternateColor": "c60c30",
        "logos": [{"href": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png"}],
    }

    @patch("pickem_api.management.commands.update_records.fetch_team_record")
    @patch("pickem_api.management.commands.update_records.fetch_team_list")
    def test_creates_and_updates_team_record(self, mock_list, mock_record):
        from django.core.management import call_command

        mock_list.return_value = [self.SAMPLE_TEAM]
        mock_record.return_value = (11, 3, 0)

        call_command("update_records", season=2526)

        team = Teams.objects.get(id=17)
        self.assertEqual(team.gameseason, 2526)
        self.assertEqual(team.teamNameSlug, "new-england-patriots")
        self.assertEqual((team.teamWins, team.teamLosses, team.teamTies), (11, 3, 0))
        self.assertEqual(team.teamLogo, self.SAMPLE_TEAM["logos"][0]["href"])
        self.assertEqual(team.color, "002244")

        # A second run with a new record updates the existing row (no duplicate).
        mock_record.return_value = (12, 3, 0)
        call_command("update_records", season=2526)
        self.assertEqual(Teams.objects.filter(id=17).count(), 1)
        self.assertEqual(Teams.objects.get(id=17).teamWins, 12)

    def test_season_start_year_conversion(self):
        from pickem_api.management.commands.update_records import season_start_year

        self.assertEqual(season_start_year(2526), 2025)
        self.assertEqual(season_start_year(2425), 2024)


class UpdateRankingsCommandTest(TestCase):
    """Pool-aware `update_rankings` management command (replaces cron_update_rankings.py)."""

    def _pool(self, slug):
        family = Family.objects.create(name=slug, slug=slug, status=Family.Status.ACTIVE)
        return Pool.objects.create(
            family=family, name="Pool", slug=slug, season=2526,
            competition="nfl", status=Pool.Status.ACTIVE, is_default=True,
        )

    def _sp(self, pool, email, points):
        return userSeasonPoints.objects.create(
            pool=pool, gameseason=2526, userEmail=email, userID=email,
            total_points=points,
        )

    def test_rankings_are_per_pool_with_tie_handling(self):
        from django.core.management import call_command

        pool_a = self._pool("family-a")
        pool_b = self._pool("family-b")
        # Pool A: 100, 100 (tie), 95  -> ranks 1, 1, 3
        a1 = self._sp(pool_a, "a1@x.com", 100)
        a2 = self._sp(pool_a, "a2@x.com", 100)
        a3 = self._sp(pool_a, "a3@x.com", 95)
        # Pool B ranked independently: 50, 40 -> ranks 1, 2
        b1 = self._sp(pool_b, "b1@x.com", 50)
        b2 = self._sp(pool_b, "b2@x.com", 40)

        call_command("update_rankings", season=2526)

        for entry in (a1, a2, a3, b1, b2):
            entry.refresh_from_db()

        self.assertEqual({a1.current_rank, a2.current_rank}, {1})
        self.assertEqual(a3.current_rank, 3)
        # Pool B is independent: its top user is rank 1 despite fewer points.
        self.assertEqual(b1.current_rank, 1)
        self.assertEqual(b2.current_rank, 2)


class UpdatePicksCommandTest(TestCase):
    """ORM-based `update_picks` scoring command (replaces cron_update_picks.py)."""

    def _pool(self, slug):
        family = Family.objects.create(name=slug, slug=slug, status=Family.Status.ACTIVE)
        return Pool.objects.create(
            family=family, name="Pool", slug=slug, season=2526,
            competition="nfl", status=Pool.Status.ACTIVE, is_default=True,
        )

    def _game(self, gid, slug, winner, status="finished", home_score=None, away_score=None):
        return GamesAndScores.objects.create(
            id=gid, slug=slug, competition="nfl", gameWeek="1", gameyear="2025",
            gameseason=2526, startTimestamp=timezone.now(), statusType=status,
            statusTitle="Final", gameWinner=winner, gameScored=False,
            homeTeamId=1, homeTeamSlug="eagles", homeTeamName="Eagles",
            homeTeamScore=home_score, awayTeamScore=away_score,
            awayTeamId=2, awayTeamSlug="chiefs", awayTeamName="Chiefs",
        )

    def _pick(self, pid, pool, game, pick):
        return GamePicks.objects.create(
            id=pid, pool=pool, pick_game_id=game.id, slug=game.slug,
            userID=pid, gameWeek="1", gameyear="2025", gameseason=2526,
            competition="nfl", pick=pick, pick_correct=False,
        )

    def test_scores_correct_picks_across_pools_and_marks_game_scored(self):
        from django.core.management import call_command

        pool_a, pool_b = self._pool("fa"), self._pool("fb")
        game = self._game(100, "eagles-chiefs", winner="eagles")
        # Correct in pool A, wrong in pool B, correct again in pool B.
        a_ok = self._pick("1-1-100", pool_a, game, "eagles")
        b_wrong = self._pick("2-2-100", pool_b, game, "chiefs")
        b_ok = self._pick("2-3-100", pool_b, game, "eagles")
        # A finished game with no winner yet must be left unscored.
        no_winner = self._game(200, "jets-bills", winner=None)
        pending = self._pick("1-1-200", pool_a, no_winner, "jets")

        call_command("update_picks", season=2526)

        for obj in (a_ok, b_wrong, b_ok, pending, game, no_winner):
            obj.refresh_from_db()

        self.assertTrue(a_ok.pick_correct)
        self.assertTrue(b_ok.pick_correct)
        self.assertFalse(b_wrong.pick_correct)
        self.assertTrue(game.gameScored)
        # Winnerless game untouched.
        self.assertFalse(no_winner.gameScored)
        self.assertFalse(pending.pick_correct)

    def test_finished_tie_is_marked_scored_so_the_week_can_complete(self):
        from django.core.management import call_command

        pool = self._pool("fa")
        # Real NFL tie: finished, no winner, equal populated scores.
        tie = self._game(300, "eagles-chiefs-tie", winner=None, home_score=20, away_score=20)
        picker = self._pick("1-1-300", pool, tie, "eagles")
        # Winner still pending (no scores yet) stays unscored, unchanged.
        pending_game = self._game(301, "jets-bills", winner=None)

        call_command("update_picks", season=2526)

        tie.refresh_from_db()
        picker.refresh_from_db()
        pending_game.refresh_from_db()
        self.assertTrue(tie.gameScored)
        self.assertFalse(picker.pick_correct)  # nobody picked a tie
        self.assertFalse(pending_game.gameScored)


class UpdateStandingsCommandTest(TestCase):
    """Pool-aware `update_standings` command (replaces cron_update_standings.py)."""

    def _pool(self, slug):
        family = Family.objects.create(name=slug, slug=slug, status=Family.Status.ACTIVE)
        return Pool.objects.create(
            family=family, name="Pool", slug=slug, season=2526,
            competition="nfl", status=Pool.Status.ACTIVE, is_default=True,
        )

    def _pick(self, pid, pool, uid, week, correct):
        return GamePicks.objects.create(
            id=pid, pool=pool, pick_game_id=int(pid.split("-")[-1]), slug=f"g{pid}",
            userID=uid, userEmail=f"{uid}@x.com", gameWeek=str(week), gameyear="2025",
            gameseason=2526, competition="nfl", pick="eagles", pick_correct=correct,
        )

    def test_recomputes_points_per_pool_and_folds_bonus_into_total(self):
        from django.core.management import call_command

        pool_a, pool_b = self._pool("fa"), self._pool("fb")
        self._pick("a-1-101", pool_a, "u1", 1, True)
        self._pick("a-1-102", pool_a, "u1", 1, True)
        self._pick("a-1-103", pool_a, "u1", 1, False)
        self._pick("a-1-201", pool_a, "u1", 2, True)
        self._pick("b-1-101", pool_b, "u1", 1, True)

        userSeasonPoints.objects.create(
            pool=pool_a, userID="u1", userEmail="u1@x.com", gameseason=2526,
            week_1_bonus=5,
        )

        call_command("update_standings", season=2526)

        a_row = userSeasonPoints.objects.get(pool=pool_a, userID="u1")
        self.assertEqual(a_row.week_1_points, 2)
        self.assertEqual(a_row.week_2_points, 1)
        self.assertEqual(a_row.total_points, 2 + 1 + 5)

        b_row = userSeasonPoints.objects.get(pool=pool_b, userID="u1")
        self.assertEqual(b_row.week_1_points, 1)
        self.assertEqual(b_row.total_points, 1)

    def test_honors_pool_win_points_and_tie_points(self):
        from django.core.management import call_command

        pool = self._pool("fw")
        PoolSettings.objects.create(pool=pool, win_points=3, tie_points=1)
        # Two correct picks at 3 points each.
        self._pick("w-1-101", pool, "u1", 1, True)
        self._pick("w-1-102", pool, "u1", 1, True)
        # A pick on a game that ended in a tie earns tie_points.
        GamesAndScores.objects.create(
            id=555, slug="tie-game", competition="nfl", gameWeek="1",
            gameyear="2025", gameseason=2526, startTimestamp=timezone.now(),
            statusType="finished", statusTitle="Final", gameWinner=None,
            gameScored=True, homeTeamId=1, homeTeamSlug="eagles",
            homeTeamName="Eagles", homeTeamScore=17, awayTeamScore=17,
            awayTeamId=2, awayTeamSlug="chiefs", awayTeamName="Chiefs",
        )
        GamePicks.objects.create(
            id="w-1-555", pool=pool, pick_game_id=555, slug="tie-game",
            userID="u1", userEmail="u1@x.com", gameWeek="1", gameyear="2025",
            gameseason=2526, competition="nfl", pick="eagles", pick_correct=False,
        )
        # A plain wrong pick (game not tied) earns nothing.
        self._pick("w-1-103", pool, "u1", 1, False)

        call_command("update_standings", season=2526)

        row = userSeasonPoints.objects.get(pool=pool, userID="u1")
        self.assertEqual(row.week_1_points, 3 + 3 + 1)
        self.assertEqual(row.total_points, 7)


class UpdateMissedPicksCommandTest(TestCase):
    """`update_missed_picks` — applies each pool's missed-pick policy."""

    def setUp(self):
        self.family = Family.objects.create(
            name="mp-fam", slug="mp-fam", status=Family.Status.ACTIVE
        )
        self.pool = Pool.objects.create(
            family=self.family, name="Pool", slug="mp-pool", season=2526,
            competition="nfl", status=Pool.Status.ACTIVE, is_default=True,
        )
        self.picker = User.objects.create_user("mp-picker", email="picker@x.com", password="x")
        self.slacker = User.objects.create_user("mp-slacker", email="slacker@x.com", password="x")
        for user in (self.picker, self.slacker):
            FamilyMembership.objects.create(
                family=self.family, user=user,
                role=FamilyMembership.Role.MEMBER,
                status=FamilyMembership.Status.ACTIVE,
            )

    def _game(self, gid, *, started=True, scored=False, home_prob=None, away_prob=None):
        start = timezone.now() + timedelta(hours=-1 if started else 6)
        return GamesAndScores.objects.create(
            id=gid, slug=f"g{gid}", competition="nfl", gameWeek="1",
            gameyear="2025", gameseason=2526, startTimestamp=start,
            statusType="inprogress" if started else "notstarted",
            statusTitle="", gameScored=scored,
            homeTeamId=1, homeTeamSlug="eagles", homeTeamName="Eagles",
            awayTeamId=2, awayTeamSlug="chiefs", awayTeamName="Chiefs",
            homeTeamWinProbability=home_prob, awayTeamWinProbability=away_prob,
        )

    def test_auto_home_fills_only_missing_picks_on_started_games(self):
        from django.core.management import call_command

        PoolSettings.objects.create(
            pool=self.pool,
            missed_pick_policy=PoolSettings.MissedPickPolicy.AUTO_HOME,
        )
        started = self._game(100, started=True)
        upcoming = self._game(101, started=False)
        already_scored = self._game(102, started=True, scored=True)
        real_pick = GamePicks.objects.create(
            id=f"{self.pool.id}-{self.picker.id}-100", pool=self.pool,
            pick_game_id=100, slug="g100", uid=self.picker.id,
            userID=str(self.picker.id), gameWeek="1", gameyear="2025",
            gameseason=2526, competition="nfl", pick="chiefs",
        )

        call_command("update_missed_picks", season=2526)

        auto = GamePicks.objects.get(userID=str(self.slacker.id), pick_game_id=100)
        self.assertEqual(auto.pick, "eagles")  # home team
        self.assertTrue(auto.auto_pick)
        self.assertEqual(auto.pool, self.pool)
        # The member's own pick is untouched.
        real_pick.refresh_from_db()
        self.assertEqual(real_pick.pick, "chiefs")
        self.assertFalse(real_pick.auto_pick)
        # Not-started and already-scored games get no auto picks.
        self.assertFalse(
            GamePicks.objects.filter(pick_game_id__in=[upcoming.id, already_scored.id]).exists()
        )
        # Idempotent: a second run creates nothing new.
        call_command("update_missed_picks", season=2526)
        self.assertEqual(
            GamePicks.objects.filter(userID=str(self.slacker.id)).count(), 1
        )

    def test_auto_favorite_picks_the_probable_winner_with_home_fallback(self):
        from django.core.management import call_command

        PoolSettings.objects.create(
            pool=self.pool,
            missed_pick_policy=PoolSettings.MissedPickPolicy.AUTO_FAVORITE,
        )
        away_favored = self._game(200, home_prob=35.0, away_prob=65.0)
        no_odds = self._game(201)

        call_command("update_missed_picks", season=2526)

        self.assertEqual(
            GamePicks.objects.get(userID=str(self.slacker.id), pick_game_id=200).pick,
            "chiefs",
        )
        self.assertEqual(
            GamePicks.objects.get(userID=str(self.slacker.id), pick_game_id=201).pick,
            "eagles",
        )

    def test_zero_points_policy_creates_nothing(self):
        from django.core.management import call_command

        PoolSettings.objects.create(pool=self.pool)  # default zero_points
        self._game(300, started=True)

        call_command("update_missed_picks", season=2526)

        self.assertFalse(GamePicks.objects.exists())


class UpdateSeasonWinnersCommandTest(TestCase):
    """`update_season_winners` — crowns year_winner once the season completes."""

    def setUp(self):
        self.family = Family.objects.create(
            name="sw-fam", slug="sw-fam", status=Family.Status.ACTIVE
        )
        self.pool = Pool.objects.create(
            family=self.family, name="Pool", slug="sw-pool", season=2526,
            competition="nfl", status=Pool.Status.ACTIVE, is_default=True,
        )

    def _final_week_game(self, *, scored=True):
        return GamesAndScores.objects.create(
            id=1800, slug="final-game", competition="nfl", gameWeek="18",
            gameyear="2026", gameseason=2526, startTimestamp=timezone.now(),
            statusType="finished", statusTitle="Final", gameWinner="eagles",
            gameScored=scored,
            homeTeamId=1, homeTeamSlug="eagles", homeTeamName="Eagles",
            awayTeamId=2, awayTeamSlug="chiefs", awayTeamName="Chiefs",
        )

    def _row(self, user_id, total, *, week18_points=0, week18_winner=False):
        return userSeasonPoints.objects.create(
            pool=self.pool, userID=user_id, userEmail=f"{user_id}@x.com",
            gameseason=2526, total_points=total,
            week_18_points=week18_points, week_18_winner=week18_winner,
        )

    def test_crowns_top_total_once_final_week_complete(self):
        from django.core.management import call_command

        self._final_week_game(scored=True)
        leader = self._row("u1", 30, week18_points=3, week18_winner=True)
        runner_up = self._row("u2", 20)

        call_command("update_season_winners", season=2526)

        leader.refresh_from_db()
        runner_up.refresh_from_db()
        self.assertTrue(leader.year_winner)
        self.assertFalse(runner_up.year_winner)
        audits = FamilyAuditLog.objects.filter(target_id="season_2526")
        self.assertEqual(audits.count(), 1)

        # Idempotent: no second audit entry once crowned.
        call_command("update_season_winners", season=2526)
        self.assertEqual(
            FamilyAuditLog.objects.filter(target_id="season_2526").count(), 1
        )

    def test_ties_produce_co_champions(self):
        from django.core.management import call_command

        self._final_week_game(scored=True)
        first = self._row("u1", 30, week18_points=3, week18_winner=True)
        second = self._row("u2", 30)

        call_command("update_season_winners", season=2526)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.year_winner)
        self.assertTrue(second.year_winner)

    def test_skips_when_final_week_incomplete_or_bonus_not_awarded(self):
        from django.core.management import call_command

        # Final week game exists but isn't scored yet.
        game = self._final_week_game(scored=False)
        row = self._row("u1", 30, week18_points=3, week18_winner=False)

        call_command("update_season_winners", season=2526)
        row.refresh_from_db()
        self.assertFalse(row.year_winner)

        # Week complete, but the week-18 winner bonus hasn't landed yet:
        # totals aren't final, so hold off.
        game.gameScored = True
        game.save(update_fields=["gameScored"])
        call_command("update_season_winners", season=2526)
        row.refresh_from_db()
        self.assertFalse(row.year_winner)

        # Once the weekly award exists, the crown lands.
        row.week_18_winner = True
        row.save(update_fields=["week_18_winner"])
        call_command("update_season_winners", season=2526)
        row.refresh_from_db()
        self.assertTrue(row.year_winner)


class UpdateGamesCommandTest(TestCase):
    """ORM-based `update_games` command (replaces cron_update_games_v2.py)."""

    PAYLOAD = {
        "week": {"number": 1},
        "events": [{
            "weather": {"temperature": 60, "displayValue": "Clear"},
            "links": [{"text": "Gamecast", "href": "http://gc"}],
            "competitions": [{
                "id": "401",
                "date": "2025-09-08T00:20Z",
                "status": {"type": {"name": "STATUS_FINAL",
                                    "description": "Final", "detail": "Final"}},
                "venue": {"indoor": True},
                "odds": [{"spread": -3, "overUnder": 45,
                          "homeTeamOdds": {"favorite": True},
                          "awayTeamOdds": {"favorite": False}}],
                "broadcasts": [{"names": ["CBS"]}],
                "competitors": [
                    {"homeAway": "home", "id": "1", "team": {"displayName": "Home Team"},
                     "winner": True, "score": "24",
                     "linescores": [{"value": 7}, {"value": 7}, {"value": 3}, {"value": 7}]},
                    {"homeAway": "away", "id": "2", "team": {"displayName": "Away Team"},
                     "winner": False, "score": "20",
                     "linescores": [{"value": 3}, {"value": 7}, {"value": 7}, {"value": 3}]},
                ],
            }],
        }],
    }

    def setUp(self):
        Teams.objects.create(id=1, teamNameSlug="home", teamNameName="Home Team")
        Teams.objects.create(id=2, teamNameSlug="away", teamNameName="Away Team")

    @patch("pickem_api.management.commands.update_games.fetch_scoreboard")
    def test_upserts_game_with_scores_odds_and_weather(self, mock_fetch):
        from django.core.management import call_command

        mock_fetch.return_value = self.PAYLOAD
        call_command("update_games", season=2526, week=1)

        game = GamesAndScores.objects.get(id=401)
        self.assertEqual(game.statusType, "finished")
        self.assertEqual(game.gameWinner, "home")
        self.assertEqual(game.slug, "home-away")
        self.assertEqual(game.gameseason, 2526)
        self.assertEqual(game.gameyear, "2025")
        self.assertEqual(game.homeTeamScore, 24)
        self.assertEqual(game.homeTeamPeriod1, 7)
        self.assertEqual(game.awayTeamScore, 20)
        self.assertEqual(game.spread, -3)
        self.assertEqual(game.weatherCondition, "Clear")
        self.assertTrue(game.venueIndoor)
        self.assertEqual(game.broadcast, "CBS")
        self.assertEqual(game.gamecastUrl, "http://gc")
        # Home favorite by 3: probability boosted above 50.
        self.assertGreater(game.homeTeamWinProbability, 50)

        # Idempotent: a re-run updates the same row, no duplicate.
        mock_fetch.return_value = self.PAYLOAD
        call_command("update_games", season=2526, week=1)
        self.assertEqual(GamesAndScores.objects.filter(id=401).count(), 1)

    def test_parse_scoreboard_skips_malformed_competition_and_continues(self):
        from pickem_api.management.commands.update_games import parse_scoreboard

        payload = {
            "week": {"number": 1},
            "events": [
                {
                    "id": "bad-event",
                    "competitions": [
                        {
                            "id": "999",
                            "date": "2025-09-08T00:20Z",
                            # Missing status / competitors on purpose.
                        }
                    ],
                },
                self.PAYLOAD["events"][0],
            ],
        }

        parsed = list(parse_scoreboard(payload, season=2526, game_year=2025))

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0][0], 401)

    def test_parse_scoreboard_skips_finished_game_with_missing_score(self):
        # A flapping ESPN poll reports FINAL but drops a score; writing it would
        # null out a good final, so it must be skipped, not yielded.
        from pickem_api.management.commands.update_games import parse_scoreboard
        import copy

        payload = copy.deepcopy(self.PAYLOAD)
        payload["events"][0]["competitions"][0]["competitors"][0]["score"] = None

        parsed = list(parse_scoreboard(payload, season=2526, game_year=2025))

        self.assertEqual(parsed, [])

    def test_parse_scoreboard_maps_overtime_final_to_finished(self):
        from pickem_api.management.commands.update_games import parse_scoreboard
        import copy

        payload = copy.deepcopy(self.PAYLOAD)
        payload["events"][0]["competitions"][0]["status"]["type"]["name"] = "STATUS_FINAL_OVERTIME"

        parsed = list(parse_scoreboard(payload, season=2526, game_year=2025))

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0][1]["statusType"], "finished")


class UpdateAllCommandTest(TestCase):
    @patch("pickem_api.management.commands.update_all.call_command")
    def test_raises_command_error_when_any_pipeline_step_fails(self, mock_call_command):
        from django.core.management import call_command
        from pickem_api.management.commands.update_all import PIPELINE

        def side_effect(command, **_kwargs):
            if command == "update_games":
                raise RuntimeError("espn down")
            return None

        mock_call_command.side_effect = side_effect

        with self.assertRaisesMessage(
            CommandError, "Pipeline finished with 1 failed step(s)."
        ):
            call_command("update_all", season=2526)

        self.assertEqual(mock_call_command.call_count, len(PIPELINE))


class VestigialApiWriteRemovalTests(TestCase):
    def setUp(self):
        self.client = Client()
        currentSeason.objects.create(season=2526, display_name="2025-2026")
        self.staff = User.objects.create_user(
            username="api-staff", email="api-staff@example.com", password="pass", is_staff=True
        )
        self.client.force_login(self.staff)
        self.game = GamesAndScores.objects.create(
            id=1234,
            slug="away-home-week-1",
            competition="nfl",
            gameWeek="1",
            gameyear="2025",
            gameseason=2526,
            startTimestamp=timezone.now(),
            statusType="notstarted",
            statusTitle="Scheduled",
            homeTeamId=1,
            homeTeamSlug="home",
            homeTeamName="Home",
            awayTeamId=2,
            awayTeamSlug="away",
            awayTeamName="Away",
        )
        self.week = GameWeeks.objects.create(
            weekNumber=1,
            date=date(2025, 9, 7),
            season=2526,
        )

    def test_games_api_is_read_only(self):
        post = self.client.post(
            "/api/games",
            data="{}",
            content_type="application/json",
        )
        delete = self.client.delete("/api/games")
        put = self.client.put(
            f"/api/games/{self.game.id}",
            data="{}",
            content_type="application/json",
        )
        patch_response = self.client.patch(
            f"/api/games/{self.game.id}",
            data="{}",
            content_type="application/json",
        )
        detail_delete = self.client.delete(f"/api/games/{self.game.id}")

        self.assertEqual(post.status_code, 405)
        self.assertEqual(delete.status_code, 405)
        self.assertEqual(put.status_code, 405)
        self.assertEqual(patch_response.status_code, 405)
        self.assertEqual(detail_delete.status_code, 405)

    def test_weeks_api_is_read_only(self):
        post = self.client.post(
            "/api/weeks",
            data="{}",
            content_type="application/json",
        )
        delete = self.client.delete("/api/weeks")
        detail_delete = self.client.delete(f"/api/weeks/{self.week.date.isoformat()}")

        self.assertEqual(post.status_code, 405)
        self.assertEqual(delete.status_code, 405)
        self.assertEqual(detail_delete.status_code, 405)


class PickemApiConfigReadyTest(TestCase):
    @patch("pickem_api.scheduler.start")
    def test_ready_starts_scheduler_only_for_runserver_child(self, mock_start):
        from pickem_api.apps import PickemApiConfig

        config = PickemApiConfig("pickem_api", import_module("pickem_api"))

        with patch.dict(
            "os.environ",
            {
                "RUN_SCHEDULER": "true",
                "RUN_WEB_SERVER": "true",
                "RUN_MAIN": "true",
            },
            clear=False,
        ):
            with patch("sys.argv", ["manage.py", "runserver"]):
                config.ready()

        mock_start.assert_called_once_with()

    @patch("pickem_api.scheduler.start")
    def test_ready_skips_scheduler_for_non_web_or_parent_processes(self, mock_start):
        from pickem_api.apps import PickemApiConfig

        config = PickemApiConfig("pickem_api", import_module("pickem_api"))

        with patch.dict(
            "os.environ",
            {
                "RUN_SCHEDULER": "true",
                "RUN_WEB_SERVER": "true",
            },
            clear=False,
        ):
            with patch("sys.argv", ["manage.py", "migrate"]):
                config.ready()
            with patch("sys.argv", ["manage.py", "runserver"]):
                config.ready()

        mock_start.assert_not_called()

    @patch("pickem_api.scheduler.BackgroundScheduler")
    def test_start_registers_the_orchestrator_and_prune_jobs(self, mock_scheduler_cls):
        import pickem_api.scheduler as scheduler_module

        scheduler_module._scheduler = None
        scheduler = mock_scheduler_cls.return_value
        try:
            started = scheduler_module.start()

            self.assertEqual(started, scheduler)
            # Everything now runs through the single orchestrator tick; only it
            # and the daily prune are registered as APScheduler jobs.
            job_names = [call.kwargs["name"] for call in scheduler.add_job.call_args_list]
            self.assertIn("Pipeline orchestrator", job_names)
            self.assertIn("Prune superadmin logs", job_names)
            job_ids = [call.kwargs["id"] for call in scheduler.add_job.call_args_list]
            self.assertIn("pipeline_tick", job_ids)
        finally:
            scheduler_module._scheduler = None


class WeeklyWinnerEngineTest(TestCase):
    """Weekly winner engine: strategies, tie chains, idempotency, triggering."""

    class StubStats:
        """GameStatsProvider stand-in — no network."""
        def __init__(self, yards=700):
            self.yards = yards
            self.calls = 0

        def combined_yards(self, game_id):
            self.calls += 1
            return self.yards

    def setUp(self):
        self.family = Family.objects.create(name="Smith", slug="smith")
        self.pool = Pool.objects.create(
            family=self.family, name="Pool", slug="main", season=2526,
            competition="nfl", status=Pool.Status.ACTIVE, is_default=True,
        )
        self.settings = PoolSettings.objects.create(pool=self.pool)
        # Week 1: one ordinary game and the (later) MNF tiebreaker game.
        GamesAndScores.objects.create(
            id=900, slug="a-b", competition="nfl", gameWeek="1", gameyear="2025",
            gameseason=2526, startTimestamp=timezone.now(), statusType="finished",
            statusTitle="Final", gameScored=True,
            homeTeamId=1, homeTeamSlug="a", homeTeamName="A",
            awayTeamId=2, awayTeamSlug="b", awayTeamName="B",
        )
        self.mnf = GamesAndScores.objects.create(
            id=901, slug="c-d", competition="nfl", gameWeek="1", gameyear="2025",
            gameseason=2526, startTimestamp=timezone.now() + timedelta(days=1),
            statusType="finished", statusTitle="Final", gameScored=True,
            tieBreakerGame=True, homeTeamScore=24, awayTeamScore=20,
            homeTeamId=3, homeTeamSlug="c", homeTeamName="C",
            awayTeamId=4, awayTeamSlug="d", awayTeamName="D",
        )

    def _player(self, uid, week1_points):
        return userSeasonPoints.objects.create(
            pool=self.pool, gameseason=2526, userID=uid,
            userEmail=f"{uid}@x.com", week_1_points=week1_points,
        )

    def _tb_pick(self, uid, score=None, yards=None):
        return GamePicks.objects.create(
            id=f"{self.pool.id}-{uid}-901", pool=self.pool, pick_game_id=901,
            slug="c-d", userID=uid, gameWeek="1", gameyear="2025",
            gameseason=2526, competition="nfl", pick="c",
            tieBreakerScore=score, tieBreakerYards=yards,
        )

    def _award(self, stats=None, **kwargs):
        from pickem_api.weekly_winners import award_weekly_winners
        return award_weekly_winners(
            self.pool, 2526, 1, stats_provider=stats or self.StubStats(), **kwargs
        )

    def test_outright_winner_gets_flag_bonus_total_and_audit(self):
        top = self._player("u1", 10)
        other = self._player("u2", 7)

        result = self._award()

        top.refresh_from_db(); other.refresh_from_db()
        self.assertEqual(result["winners"], ["u1"])
        self.assertEqual(result["method"], "top_score")
        self.assertTrue(top.week_1_winner)
        self.assertEqual(top.week_1_bonus, 2)      # default weekly_winner_points
        self.assertEqual(top.total_points, 12)     # 10 + 2
        self.assertFalse(other.week_1_winner)
        self.assertEqual(other.total_points, 7)
        audit = FamilyAuditLog.objects.get(
            pool=self.pool, action=FamilyAuditLog.Action.WEEK_WINNER_UPDATED
        )
        self.assertEqual(audit.metadata["winners"], ["u1"])

    def test_tie_resolved_by_closest_total_score(self):
        a = self._player("u1", 9); b = self._player("u2", 9)
        self._tb_pick("u1", score=41)   # off by 3 (actual 44)
        self._tb_pick("u2", score=50)   # off by 6

        result = self._award()

        self.assertEqual(result["winners"], ["u1"])
        self.assertEqual(result["method"], "total_score")
        a.refresh_from_db(); b.refresh_from_db()
        self.assertTrue(a.week_1_winner); self.assertFalse(b.week_1_winner)

    def test_primary_dead_heat_falls_to_secondary_yards_via_provider(self):
        self._player("u1", 9); self._player("u2", 9)
        self._tb_pick("u1", score=42, yards=690)   # scores equidistant (both off 2)
        self._tb_pick("u2", score=46, yards=800)   # yards: u1 off 10, u2 off 100
        stats = self.StubStats(yards=700)

        result = self._award(stats=stats)

        self.assertEqual(result["winners"], ["u1"])
        self.assertEqual(result["method"], "combined_yards")
        self.assertEqual(stats.calls, 1)  # ESPN hit exactly once, lazily

    def test_unresolvable_tie_produces_co_winners_with_full_bonus(self):
        a = self._player("u1", 9); b = self._player("u2", 9)
        # No tiebreaker predictions at all -> chain can't narrow.
        result = self._award()

        self.assertEqual(result["winners"], ["u1", "u2"])
        a.refresh_from_db(); b.refresh_from_db()
        self.assertTrue(a.week_1_winner and b.week_1_winner)
        self.assertEqual((a.week_1_bonus, b.week_1_bonus), (2, 2))

    def test_split_points_secondary_divides_bonus(self):
        self.settings.secondary_tiebreaker = "split_points"
        self.settings.weekly_winner_points = 5
        self.settings.save()
        a = self._player("u1", 9); b = self._player("u2", 9)
        self._tb_pick("u1", score=42); self._tb_pick("u2", score=46)  # dead heat

        result = self._award()

        self.assertEqual(result["winners"], ["u1", "u2"])
        self.assertEqual(result["bonus_each"], 2)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(a.week_1_bonus + b.week_1_bonus, 5)
        self.assertEqual((a.week_1_bonus, b.week_1_bonus), (3, 2))

    def test_force_rerun_zeroes_non_winner_bonus_instead_of_nulling_it(self):
        winner = self._player("u1", 10)
        loser = self._player("u2", 7)
        loser.week_1_bonus = 4
        loser.total_points = 11
        loser.save(update_fields=["week_1_bonus", "total_points"])

        self._award(force=True)

        winner.refresh_from_db(); loser.refresh_from_db()
        self.assertEqual(winner.week_1_bonus, 2)
        self.assertEqual(loser.week_1_bonus, 0)
        self.assertEqual(loser.total_points, 7)

    def test_missing_combined_yards_actual_does_not_latch_co_winners(self):
        self.settings.primary_tiebreaker = "combined_yards"
        self.settings.secondary_tiebreaker = "split_points"
        self.settings.save()
        a = self._player("u1", 9); b = self._player("u2", 9)
        self._tb_pick("u1", yards=700)
        self._tb_pick("u2", yards=710)

        class MissingYards:
            def combined_yards(self, game_id):
                raise RuntimeError("espn blip")

        result = self._award(stats=MissingYards())

        self.assertIsNone(result)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertFalse(a.week_1_winner)
        self.assertFalse(b.week_1_winner)
        self.assertIsNone(a.week_1_bonus)
        self.assertIsNone(b.week_1_bonus)

    def test_coin_flip_is_deterministic_across_forced_reruns(self):
        self.settings.secondary_tiebreaker = "coin_flip"
        self.settings.save()
        self._player("u1", 9); self._player("u2", 9)

        first = self._award()
        second = self._award(force=True)

        self.assertEqual(len(first["winners"]), 1)
        self.assertEqual(first["winners"], second["winners"])

    def test_no_over_variant_unresolved_when_everyone_goes_over(self):
        self.settings.primary_tiebreaker = "total_score_no_over"
        self.settings.save()
        self._player("u1", 9); self._player("u2", 9)
        self._tb_pick("u1", score=45, yards=650)  # both OVER 44
        self._tb_pick("u2", score=60, yards=710)
        stats = self.StubStats(yards=700)

        result = self._award(stats=stats)

        # Primary can't apply (Price is Right bust) -> secondary yards decides.
        self.assertEqual(result["winners"], ["u2"])
        self.assertEqual(result["method"], "combined_yards")

    def test_candidate_without_prediction_loses_to_one_with_prediction(self):
        self._player("u1", 9); self._player("u2", 9)
        self._tb_pick("u1", score=30)  # only u1 predicted

        result = self._award()

        self.assertEqual(result["winners"], ["u1"])

    def test_allow_tiebreaker_off_means_co_winners(self):
        self.settings.allow_tiebreaker = False
        self.settings.save()
        self._player("u1", 9); self._player("u2", 9)
        self._tb_pick("u1", score=44)  # would win the tiebreak — must be ignored

        result = self._award()

        self.assertEqual(result["winners"], ["u1", "u2"])
        self.assertEqual(result["method"], "co_winners")

    def test_idempotent_second_run_is_a_noop(self):
        top = self._player("u1", 10)

        self.assertIsNotNone(self._award())
        self.assertIsNone(self._award())  # already awarded

        top.refresh_from_db()
        self.assertEqual(top.total_points, 12)  # bonus not applied twice

    def test_nothing_awarded_when_nobody_scored(self):
        self._player("u1", 0)
        self.assertIsNone(self._award())

    def test_command_waits_for_week_completion(self):
        from django.core.management import call_command
        from io import StringIO

        self._player("u1", 10)
        self.mnf.statusType = "inprogress"  # MNF still going
        self.mnf.save(update_fields=["statusType"])

        out = StringIO()
        call_command("update_weekly_winners", season=2526, stdout=out)
        self.assertIn("No completed week", out.getvalue())
        self.assertFalse(
            userSeasonPoints.objects.filter(pool=self.pool, week_1_winner=True).exists()
        )

        # MNF ends -> the same command now awards.
        self.mnf.statusType = "finished"
        self.mnf.save(update_fields=["statusType"])
        with patch(
            "pickem_api.management.commands.update_weekly_winners.EspnGameStatsProvider"
        ) as provider:
            provider.return_value = self.StubStats()
            out = StringIO()
            call_command("update_weekly_winners", season=2526, stdout=out)
        self.assertIn("awarded winners in 1 pool(s)", out.getvalue())
        self.assertTrue(
            userSeasonPoints.objects.get(pool=self.pool, userID="u1").week_1_winner
        )


class UpdateStatsCommandTest(TestCase):
    """`update_stats` command — Django replacement for the pickemctl service."""

    def _pool(self, slug):
        family = Family.objects.create(name=slug, slug=slug, status=Family.Status.ACTIVE)
        return Pool.objects.create(
            family=family, name="Pool", slug=slug, season=2526,
            competition="nfl", status=Pool.Status.ACTIVE, is_default=True,
        )

    def _game(self, gid, slug, winner="eagles", week="1", scored=True):
        return GamesAndScores.objects.create(
            id=gid, slug=slug, competition="nfl", gameWeek=week, gameyear="2025",
            gameseason=2526, startTimestamp=timezone.now(), statusType="finished",
            statusTitle="Final", gameWinner=winner, gameScored=scored,
            homeTeamId=1, homeTeamSlug="eagles", homeTeamName="Eagles",
            awayTeamId=2, awayTeamSlug="chiefs", awayTeamName="Chiefs",
        )

    def _pick(self, user, game, pick, correct, week="1"):
        return GamePicks.objects.create(
            id=f"1-{user.id}-{game.id}", pool=self.pool, pick_game_id=game.id,
            slug=game.slug, uid=user.id, userID=str(user.id), gameWeek=week,
            gameyear="2025", gameseason=2526, competition="nfl", pick=pick,
            pick_correct=correct,
        )

    def setUp(self):
        self.pool = self._pool("stats-fam")
        self.alice = User.objects.create_user("alice-us", email="alice-us@x.com", password="x")

    def test_accuracy_weeks_won_seasons_won_and_missed_picks(self):
        from django.core.management import call_command

        g1 = self._game(1, "g1")
        g2 = self._game(2, "g2")
        self._game(3, "g3")  # scored but never picked -> a missed pick
        self._pick(self.alice, g1, "eagles", correct=True)
        self._pick(self.alice, g2, "chiefs", correct=False)
        usp = userSeasonPoints.objects.create(
            pool=self.pool, gameseason=2526, userEmail=self.alice.email,
            userID=str(self.alice.id), total_points=5, year_winner=True,
        )
        usp.week_1_winner = True
        usp.week_2_winner = True
        usp.save()

        call_command("update_stats", season=2526)

        stats = userStats.objects.get(userID=str(self.alice.id), pool__isnull=True)
        self.assertEqual(stats.correctPickTotalSeason, 1)
        self.assertEqual(stats.totalPicksSeason, 2)
        self.assertEqual(stats.pickPercentSeason, 50)
        self.assertEqual(stats.missedPicksSeason, 1)
        self.assertEqual(stats.weeksWonSeason, 2)
        self.assertEqual(stats.seasonsWon, 1)

        # Idempotent: a second run keeps a single row.
        call_command("update_stats", season=2526)
        self.assertEqual(
            userStats.objects.filter(userID=str(self.alice.id), pool__isnull=True).count(),
            1,
        )

    def test_perfect_weeks_and_most_least_picked(self):
        from django.core.management import call_command

        # Week 1: both scored games picked correctly -> a perfect week.
        g10 = self._game(10, "g10", week="1")
        g11 = self._game(11, "g11", week="1")
        self._pick(self.alice, g10, "eagles", correct=True, week="1")
        self._pick(self.alice, g11, "eagles", correct=True, week="1")
        # Week 2: one wrong -> not perfect.
        g12 = self._game(12, "g12", week="2")
        g13 = self._game(13, "g13", week="2")
        self._pick(self.alice, g12, "eagles", correct=True, week="2")
        self._pick(self.alice, g13, "chiefs", correct=False, week="2")

        call_command("update_stats", season=2526)

        # Exactly one row for the user even though they picked across two weeks
        # (guards the distinct()+default-ordering duplicate-processing gotcha).
        self.assertEqual(userStats.objects.filter(userID=str(self.alice.id)).count(), 1)
        stats = userStats.objects.get(userID=str(self.alice.id), pool__isnull=True)
        self.assertEqual(stats.perfectWeeksSeason, 1)
        # eagles picked 3x, chiefs 1x.
        self.assertEqual(stats.mostPickedSeason, "eagles")
        self.assertEqual(stats.leastPickedSeason, "chiefs")

    def test_auto_picks_count_as_missed_and_not_toward_accuracy_or_perfection(self):
        from django.core.management import call_command

        g1 = self._game(21, "g21", week="1")
        g2 = self._game(22, "g22", week="1")
        # One real correct pick; the other game was auto-filled by the pool's
        # missed-pick policy (and even scored correct).
        self._pick(self.alice, g1, "eagles", correct=True, week="1")
        auto = self._pick(self.alice, g2, "eagles", correct=True, week="1")
        auto.auto_pick = True
        auto.save(update_fields=["auto_pick"])

        call_command("update_stats", season=2526)

        stats = userStats.objects.get(userID=str(self.alice.id), pool__isnull=True)
        # Accuracy counts only the real pick.
        self.assertEqual(stats.totalPicksSeason, 1)
        self.assertEqual(stats.correctPickTotalSeason, 1)
        # The auto-filled game still reads as missed for the user.
        self.assertEqual(stats.missedPicksSeason, 1)
        # And an auto-assisted week is never perfect.
        self.assertEqual(stats.perfectWeeksSeason, 0)


class ApiEndpointAuthorizationTests(TestCase):
    """The vestigial DRF API must not leak picks/points/PII to anonymous or
    non-staff callers (the legacy cron scripts that used it are retired)."""

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user("api-member", email="m@x.com", password="p")
        self.staff = User.objects.create_user(
            "api-staff", email="s@x.com", password="p", is_staff=True
        )
        family = Family.objects.create(name="Fam", slug="fam", status=Family.Status.ACTIVE)
        pool = Pool.objects.create(
            family=family, name="Pool", slug="main", season=2526,
            competition="nfl", status=Pool.Status.ACTIVE, is_default=True,
        )
        GamePicks.objects.create(
            id="1-1-100", pool=pool, pick_game_id=100, slug="g", userID="1",
            userEmail="victim@example.com", gameWeek="1", gameyear="2025",
            gameseason=2526, competition="nfl", pick="eagles", pick_correct=True,
        )
        userSeasonPoints.objects.create(
            pool=pool, userID="1", userEmail="victim@example.com",
            gameseason=2526, gameyear="2025", total_points=10,
        )

    LEAKY_ENDPOINTS = [
        "/api/userpickids/2526/1",
        "/api/userpicks/2526/1/1",
        "/api/userpicks/1-1",
        "/api/picks/100",
        "/api/userpoints/",
        "/api/userpoints/2526/1",
        "/api/userinfo/1",
    ]

    def test_anonymous_cannot_read_picks_points_or_user_info(self):
        for path in self.LEAKY_ENDPOINTS:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertIn(response.status_code, (401, 403))

    def test_ordinary_member_cannot_read_them_either(self):
        self.client.force_login(self.member)
        for path in self.LEAKY_ENDPOINTS:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 403)

    def test_no_response_body_leaks_the_victim_email(self):
        self.client.force_login(self.member)
        for path in self.LEAKY_ENDPOINTS:
            with self.subTest(path=path):
                self.assertNotContains(
                    self.client.get(path), "victim@example.com",
                    status_code=403,
                )
