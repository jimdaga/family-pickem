from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pickem_api.models import (
    Family, GamePicks, GamesAndScores, GameWeeks, Pool, PoolSettings, currentSeason,
)
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

    def test_season_update_collapses_duplicate_currentseason_rows(self):
        """currentSeason has no DB uniqueness constraint. If stray duplicates
        exist, a season update must leave exactly one row so get_season()'s
        .first() is deterministic."""
        currentSeason.objects.create(season=2627, display_name='2026-2027')
        currentSeason.objects.create(season=2627, display_name='dup')
        self.assertEqual(currentSeason.objects.count(), 2)

        self.client.post(
            reverse('superadmin:season_update'),
            {'season': '2728', 'display_name': '2027-2028', 'confirm': '2728'},
        )

        self.assertEqual(currentSeason.objects.count(), 1)
        self.assertEqual(currentSeason.objects.first().season, 2728)

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

    def test_publishing_a_site_wide_banner_accepts_a_chosen_icon(self):
        self.client.post(
            reverse('superadmin:banner_publish'),
            {'title': 'Playoffs!', 'banner_type': 'success', 'icon': 'fas fa-trophy'},
        )
        banner = SiteBanner.objects.get()
        self.assertEqual(banner.icon, 'fas fa-trophy')

    def test_publishing_a_site_wide_banner_defaults_icon_when_missing(self):
        self.client.post(
            reverse('superadmin:banner_publish'),
            {'title': 'Scheduled maintenance', 'banner_type': 'warning'},
        )
        banner = SiteBanner.objects.get()
        self.assertEqual(banner.icon, 'fas fa-bullhorn')

    def test_publishing_a_site_wide_banner_rejects_an_unlisted_icon(self):
        """A POST that bypasses the <select> must not smuggle an arbitrary
        class string onto SiteBanner.icon — only BANNER_ICON_CHOICES values
        (or the default) may be persisted."""
        self.client.post(
            reverse('superadmin:banner_publish'),
            {'title': 'Sketchy icon', 'banner_type': 'info', 'icon': 'fas fa-not-a-real-icon'},
        )
        banner = SiteBanner.objects.get()
        self.assertEqual(banner.icon, 'fas fa-bullhorn')

    def test_publishing_a_banner_requires_a_title(self):
        self.client.post(reverse('superadmin:banner_publish'), {'title': ''})
        self.assertEqual(SiteBanner.objects.count(), 0)
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_deactivating_a_banner_hides_it(self):
        banner = SiteBanner.objects.create(title='Old news', family=None)
        self.client.post(reverse('superadmin:banner_deactivate', args=[banner.id]))
        banner.refresh_from_db()
        self.assertFalse(banner.is_active)

    def test_deactivating_a_banner_logs_its_own_audit_action(self):
        # A deactivation logged as BANNER_PUBLISHED would mislabel the audit
        # trail — anyone filtering by action="banner_published" would see
        # deactivations mixed in with actual publishes.
        banner = SiteBanner.objects.create(title='Old news', family=None)
        self.client.post(reverse('superadmin:banner_deactivate', args=[banner.id]))
        entry = SuperAdminAuditLog.objects.latest('created_at')
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.BANNER_DEACTIVATED)

    def test_publishing_a_site_wide_banner_rejects_an_unlisted_banner_type(self):
        """A POST that bypasses the <select> must not smuggle an arbitrary
        string onto SiteBanner.banner_type — only a value from BANNER_TYPES
        (or the default) may be persisted."""
        self.client.post(
            reverse('superadmin:banner_publish'),
            {'title': 'Sketchy type', 'banner_type': 'javascript:alert(1)'},
        )
        banner = SiteBanner.objects.get()
        self.assertEqual(banner.banner_type, 'info')

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

    def test_family_on_current_season_not_flagged(self):
        from pickem_api.models import currentSeason
        currentSeason.objects.create(season=2627, display_name='2026-2027')
        # self.pool (season 2627) is this family's latest; an older pool exists too.
        Pool.objects.create(
            family=self.family, name='Old', slug='old', season=2526,
        )
        response = self.client.get(reverse('superadmin:overview'))
        flagged = [e['family'] for e in response.context['anomalies']['families_off_season']]
        self.assertNotIn(self.family, flagged)

    def test_family_whose_latest_pool_is_stale_is_flagged(self):
        from pickem_api.models import currentSeason
        currentSeason.objects.create(season=2728, display_name='2027-2028')
        # self.family's newest pool is season 2627 < current 2728 -> stale.
        response = self.client.get(reverse('superadmin:overview'))
        flagged = {e['family'].id: e for e in response.context['anomalies']['families_off_season']}
        self.assertIn(self.family.id, flagged)
        self.assertEqual(flagged[self.family.id]['latest_pool'].season, 2627)

    def test_no_current_season_flags_nothing(self):
        response = self.client.get(reverse('superadmin:overview'))
        self.assertEqual(response.context['anomalies']['families_off_season'], [])

    def test_nav_order_jobs_logs_audit(self):
        """Nav tabs appear in order: jobs, logs, audit."""
        response = self.client.get(reverse('superadmin:overview'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        jobs_idx = html.index('>jobs<')
        logs_idx = html.index('>logs<')
        audit_idx = html.index('>audit<')
        self.assertLess(jobs_idx, logs_idx, 'jobs should appear before logs')
        self.assertLess(logs_idx, audit_idx, 'logs should appear before audit')


class PoolHealthTests(TestCase):
    """Abandoned / went-quiet / new-pool metrics on the overview."""

    def setUp(self):
        self.admin = User.objects.create_user(
            'ph-admin', email='ph@example.com', password='x', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.admin)
        currentSeason.objects.get_or_create(season=2627, defaults={'display_name': '2026-2027'})

    def _pool(self, slug, *, age_days=0, season=2627):
        family = Family.objects.create(name=slug, slug=slug)
        pool = Pool.objects.create(
            family=family, name='Main', slug=f'{slug}-pool', season=season,
            competition='nfl', status=Pool.Status.ACTIVE, is_default=True,
        )
        if age_days:
            created = timezone.now() - timedelta(days=age_days)
            Pool.objects.filter(pk=pool.pk).update(created_at=created)
            pool.refresh_from_db()
        return pool

    def _game(self, gid, week, kickoff):
        return GamesAndScores.objects.create(
            id=gid, slug=f'ph-{gid}', competition='nfl', gameWeek=str(week),
            gameyear='2026', gameseason=2627, startTimestamp=kickoff,
            statusType='notstarted', statusTitle='x',
            homeTeamId=1, homeTeamSlug='atl', homeTeamName='Atlanta',
            awayTeamId=2, awayTeamSlug='ari', awayTeamName='Arizona',
        )

    def _pick(self, pool, game, uid='1'):
        return GamePicks.objects.create(
            id=f'ph-{pool.id}-{game.id}-{uid}', pool=pool, userID=uid, uid=int(uid),
            gameseason=2627, gameWeek=game.gameWeek, competition='nfl',
            pick_game_id=game.id, pick='atl',
        )

    def _health(self):
        return self.client.get(reverse('superadmin:overview')).context['pool_health']

    def test_old_pool_with_no_picks_is_abandoned(self):
        dead = self._pool('dead', age_days=30)

        slugs = [r['pool'].slug for r in self._health()['abandoned']]

        self.assertIn(dead.slug, slugs)

    def test_new_pool_with_no_picks_is_not_abandoned(self):
        """Three of the live pools are days old -- new, not dead."""
        fresh = self._pool('fresh', age_days=2)

        slugs = [r['pool'].slug for r in self._health()['abandoned']]

        self.assertNotIn(fresh.slug, slugs)

    def test_old_pool_with_picks_is_not_abandoned(self):
        active = self._pool('activepool', age_days=30)
        self._pick(active, self._game(6001, 1, timezone.now() - timedelta(days=1)))

        slugs = [r['pool'].slug for r in self._health()['abandoned']]

        self.assertNotIn(active.slug, slugs)

    def test_a_pool_that_pre_picked_is_not_called_quiet(self):
        """The false positive that ruled out a simple recency threshold.

        Live pools submitted a whole week days in advance and then went
        legitimately silent; "no picks in N days" would flag them.
        """
        pool = self._pool('prepicker', age_days=30)
        game = self._game(6002, 1, timezone.now() - timedelta(hours=2))
        pick = self._pick(pool, game)
        # Submitted well before kickoff, then silence.
        GamePicks.objects.filter(pk=pick.pk).update(
            pickAdded=timezone.now() - timedelta(days=20)
        )

        quiet = [r['pool'].slug for r in self._health()['quiet']]

        self.assertNotIn(pool.slug, quiet)

    def test_a_pool_with_history_but_nothing_this_week_is_quiet(self):
        pool = self._pool('stopped', age_days=30)
        self._pick(pool, self._game(6003, 1, timezone.now() - timedelta(days=8)))
        # Week 2 has kicked off and this pool has not picked for it.
        self._game(6004, 2, timezone.now() - timedelta(hours=2))
        GameWeeks.objects.create(
            date=timezone.localdate(), weekNumber=2, competition='nfl', season=2627,
        )

        quiet = [r['pool'].slug for r in self._health()['quiet']]

        self.assertIn(pool.slug, quiet)

    def test_nothing_is_quiet_before_the_week_kicks_off(self):
        pool = self._pool('early', age_days=30)
        self._pick(pool, self._game(6005, 1, timezone.now() - timedelta(days=8)))
        self._game(6006, 2, timezone.now() + timedelta(days=3))   # not started
        GameWeeks.objects.create(
            date=timezone.localdate(), weekNumber=2, competition='nfl', season=2627,
        )

        self.assertEqual(self._health()['quiet'], [])

    def test_new_pools_lists_recent_signups_with_activity(self):
        recent = self._pool('recent', age_days=3)
        self._pick(recent, self._game(6007, 1, timezone.now() - timedelta(days=1)))
        old = self._pool('ancient', age_days=90)

        rows = {r['pool'].slug: r for r in self._health()['new_pools']}

        self.assertIn(recent.slug, rows)
        self.assertNotIn(old.slug, rows)
        self.assertEqual(rows[recent.slug]['picks'], 1)
        self.assertEqual(rows[recent.slug]['members'], 0)

    def test_cards_render_on_the_page(self):
        page = self.client.get(reverse('superadmin:overview'))

        for testid in ('abandoned-pools', 'quiet-pools', 'new-pools'):
            with self.subTest(card=testid):
                self.assertContains(page, f'data-testid="{testid}"')

    def test_a_pool_that_played_once_then_died_is_abandoned(self):
        """The shape the feature most needs to catch.

        An all-time pick count would exempt it forever: it HAS picks, just none
        this season. Season-scoping is what makes it visible.
        """
        pool = self._pool('diedafter', age_days=40)
        old_game = GamesAndScores.objects.create(
            id=6100, slug='ph-old', competition='nfl', gameWeek='1', gameyear='2025',
            gameseason=2526, startTimestamp=timezone.now() - timedelta(days=300),
            statusType='finished', statusTitle='Final',
            homeTeamId=1, homeTeamSlug='atl', homeTeamName='Atlanta',
            awayTeamId=2, awayTeamSlug='ari', awayTeamName='Arizona',
        )
        GamePicks.objects.create(
            id='ph-old-pick', pool=pool, userID='1', uid=1, gameseason=2526,
            gameWeek='1', competition='nfl', pick_game_id=old_game.id, pick='atl',
        )

        slugs = [r['pool'].slug for r in self._health()['abandoned']]

        self.assertIn(pool.slug, slugs)

    def test_prior_season_pools_are_not_listed_as_abandoned(self):
        """They would otherwise accumulate forever and drown the card."""
        stale = self._pool('priorseason', age_days=400, season=2526)

        slugs = [r['pool'].slug for r in self._health()['abandoned']]

        self.assertNotIn(stale.slug, slugs)

    def test_quiet_reports_not_checked_rather_than_a_false_all_clear(self):
        """No started week means nothing was verified -- saying "everyone has
        picked" would be an affirmatively false clean bill of health."""
        self._pool('somepool', age_days=30)

        health = self._health()

        self.assertFalse(health['week_checked'])
        page = self.client.get(reverse('superadmin:overview'))
        self.assertContains(page, 'Not checked')
        self.assertNotContains(page, 'Every active pool has picked this week.')

    def _count_health_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from pickem_superadmin.views.overview import _pool_health

        with CaptureQueriesContext(connection) as ctx:
            _pool_health(2627)
        return len(ctx)

    def test_pool_health_query_count_does_not_grow_with_pools(self):
        """This card sits on the landing page, which allows only cheap checks.

        Asserts constancy rather than a magic number: the number itself shifts
        with which branches are live, but it must not scale with pool count.
        Before this was collapsed it was 21 queries for 15 pools.
        """
        GameWeeks.objects.create(
            date=timezone.localdate(), weekNumber=1, competition='nfl', season=2627,
        )
        self._game(6200, 1, timezone.now() - timedelta(hours=2))
        for i in range(3):
            pool = self._pool(f'q{i}', age_days=30)
            self._pick(pool, GamesAndScores.objects.get(id=6200), uid=str(i + 1))

        with_three = self._count_health_queries()

        for i in range(3, 12):
            pool = self._pool(f'q{i}', age_days=30)
            self._pick(pool, GamesAndScores.objects.get(id=6200), uid=str(i + 1))

        self.assertEqual(self._count_health_queries(), with_three)

    def test_a_competition_that_has_not_kicked_off_is_not_called_quiet(self):
        """One competition starting says nothing about another."""
        nfl_pool = self._pool('nflpool', age_days=30)
        GameWeeks.objects.create(
            date=timezone.localdate(), weekNumber=1, competition='nfl', season=2627,
        )
        self._pick(nfl_pool, self._game(6300, 1, timezone.now() - timedelta(hours=2)))

        cfb_pool = self._pool('cfbpool', age_days=30)
        Pool.objects.filter(pk=cfb_pool.pk).update(competition='cfb')
        cfb_pool.refresh_from_db()
        GameWeeks.objects.create(
            date=timezone.localdate(), weekNumber=1, competition='cfb', season=2627,
        )
        cfb_game = GamesAndScores.objects.create(
            id=6301, slug='ph-cfb', competition='cfb', gameWeek='1', gameyear='2026',
            gameseason=2627, startTimestamp=timezone.now() + timedelta(days=2),
            statusType='notstarted', statusTitle='x',
            homeTeamId=1, homeTeamSlug='atl', homeTeamName='Atlanta',
            awayTeamId=2, awayTeamSlug='ari', awayTeamName='Arizona',
        )
        GamePicks.objects.create(
            id='ph-cfb-pick', pool=cfb_pool, userID='9', uid=9, gameseason=2627,
            gameWeek='1', competition='cfb', pick_game_id=cfb_game.id, pick='atl',
        )

        quiet = [r['pool'].slug for r in self._health()['quiet']]

        # nfl kicked off and that pool picked; cfb has not kicked off at all.
        self.assertNotIn(cfb_pool.slug, quiet)
        self.assertNotIn(nfl_pool.slug, quiet)

    def test_a_seasonless_week_row_never_outranks_a_current_season_one(self):
        """GameWeeks has no default ordering, so a lower pk must not win."""
        from pickem_superadmin.views.overview import _current_weeks_by_competition

        GameWeeks.objects.create(
            date=timezone.localdate() - timedelta(days=1), weekNumber=99,
            competition='nfl', season=None,
        )
        GameWeeks.objects.create(
            date=timezone.localdate(), weekNumber=1, competition='nfl', season=2627,
        )

        self.assertEqual(_current_weeks_by_competition(2627), {'nfl': '1'})

