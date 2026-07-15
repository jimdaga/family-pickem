from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pickem_api.models import Family, GamesAndScores, Pool, PoolSettings, currentSeason
from pickem_homepage.models import SiteBanner
from pickem_superadmin.models import SuperAdminAuditLog


class OverviewTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        self.client.force_login(self.root)

    def test_overview_shows_counts(self):
        """Migration 0074 seeds a permanent 'legacy-family-league' Family+Pool for
        pre-multi-family data, so the DB is never pristine — assert the counts
        match a fresh recount rather than pinning an exact number.

        Deliberately create an extra Pool (no extra Family) so families != pools:
        without this, both counts land on 2 (legacy row + setUp row) and a view
        bug that swaps the two querysets would still pass (2 == 2)."""
        Pool.objects.create(
            family=self.family, name='Second Pool', slug='second-pool', season=2627,
        )
        response = self.client.get(reverse('superadmin:overview'))
        self.assertEqual(response.status_code, 200)

        families_count = Family.objects.count()
        pools_count = Pool.objects.count()
        self.assertNotEqual(families_count, pools_count)

        self.assertEqual(response.context['counts']['families'], families_count)
        self.assertEqual(response.context['counts']['pools'], pools_count)
        self.assertGreaterEqual(families_count, 1)
        self.assertGreaterEqual(pools_count, 1)

    def test_overview_flags_a_pool_with_no_settings_row(self):
        response = self.client.get(reverse('superadmin:overview'))
        self.assertIn(self.pool, response.context['anomalies']['pools_without_settings'])

    def test_overview_stops_flagging_once_settings_exist(self):
        PoolSettings.objects.create(pool=self.pool)
        response = self.client.get(reverse('superadmin:overview'))
        self.assertNotIn(self.pool, response.context['anomalies']['pools_without_settings'])

    def test_backfill_action_creates_the_settings_row(self):
        self.client.post(
            reverse('superadmin:pool_settings_backfill', args=[self.pool.id]),
        )
        self.assertTrue(PoolSettings.objects.filter(pool=self.pool).exists())

    def test_updating_the_current_season_audits(self):
        currentSeason.objects.create(season=2627, display_name='2026-2027')
        self.client.post(
            reverse('superadmin:season_update'),
            {'season': '2728', 'display_name': '2027-2028', 'confirm': '2728'},
        )
        self.assertEqual(currentSeason.objects.first().season, 2728)
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.SEASON_UPDATED)
        self.assertEqual(entry.changes['season'], [2627, 2728])

    def test_season_update_requires_typed_confirmation(self):
        """get_season() drives the entire app. This is the highest-blast-radius
        field in the console, so it does not change on a stray click."""
        currentSeason.objects.create(season=2627, display_name='2026-2027')
        self.client.post(
            reverse('superadmin:season_update'),
            {'season': '2728', 'display_name': '2027-2028', 'confirm': 'wrong'},
        )
        self.assertEqual(currentSeason.objects.first().season, 2627)
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_rejected_season_update_creates_no_row_on_pristine_db(self):
        """On a DB with no currentSeason row yet, a rejected update (wrong typed
        confirmation) must write NOTHING — no blank currentSeason row, no audit
        row. Every other rejected action in this console writes nothing; season
        rejection should be no different."""
        self.assertEqual(currentSeason.objects.count(), 0)
        self.client.post(
            reverse('superadmin:season_update'),
            {'season': '2728', 'display_name': '2027-2028', 'confirm': 'wrong'},
        )
        self.assertEqual(currentSeason.objects.count(), 0)
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_publishing_a_site_wide_banner_leaves_family_null(self):
        """family=None is what makes a banner site-wide rather than one family's."""
        self.client.post(
            reverse('superadmin:banner_publish'),
            {'title': 'Scheduled maintenance Sunday', 'banner_type': 'warning'},
        )
        banner = SiteBanner.objects.get()
        self.assertIsNone(banner.family)
        self.assertTrue(banner.is_active)
        self.assertEqual(banner.title, 'Scheduled maintenance Sunday')

        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.BANNER_PUBLISHED)

    def test_publishing_a_banner_requires_a_title(self):
        self.client.post(reverse('superadmin:banner_publish'), {'title': ''})
        self.assertEqual(SiteBanner.objects.count(), 0)
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_deactivating_a_banner_hides_it(self):
        banner = SiteBanner.objects.create(title='Old news', family=None)
        self.client.post(reverse('superadmin:banner_deactivate', args=[banner.id]))
        banner.refresh_from_db()
        self.assertFalse(banner.is_active)

    def test_stuck_game_anomaly_flags_a_game_in_progress_past_kickoff(self):
        """statusType is a normalized value ('inprogress'), not a raw ESPN code, and
        the kickoff-time field is startTimestamp (there is no gameTime/gameStatus)."""
        stuck = GamesAndScores.objects.create(
            id=1,
            slug='stuck-game',
            competition='nfl',
            gameWeek='1',
            gameyear='2026',
            gameseason=2627,
            startTimestamp=timezone.now() - timezone.timedelta(hours=8),
            statusType='inprogress',
            statusTitle='In Progress',
            homeTeamId=1,
            homeTeamSlug='home',
            homeTeamName='Home Team',
            awayTeamId=2,
            awayTeamSlug='away',
            awayTeamName='Away Team',
        )
        fresh = GamesAndScores.objects.create(
            id=2,
            slug='fresh-game',
            competition='nfl',
            gameWeek='1',
            gameyear='2026',
            gameseason=2627,
            startTimestamp=timezone.now() - timezone.timedelta(hours=1),
            statusType='inprogress',
            statusTitle='In Progress',
            homeTeamId=3,
            homeTeamSlug='home2',
            homeTeamName='Home Team 2',
            awayTeamId=4,
            awayTeamSlug='away2',
            awayTeamName='Away Team 2',
        )
        finished = GamesAndScores.objects.create(
            id=3,
            slug='finished-game',
            competition='nfl',
            gameWeek='1',
            gameyear='2026',
            gameseason=2627,
            startTimestamp=timezone.now() - timezone.timedelta(hours=8),
            statusType='finished',
            statusTitle='Final',
            homeTeamId=5,
            homeTeamSlug='home3',
            homeTeamName='Home Team 3',
            awayTeamId=6,
            awayTeamSlug='away3',
            awayTeamName='Away Team 3',
        )

        response = self.client.get(reverse('superadmin:overview'))
        stuck_games = response.context['anomalies']['stuck_games']
        self.assertIn(stuck, stuck_games)
        self.assertNotIn(fresh, stuck_games)
        self.assertNotIn(finished, stuck_games)
