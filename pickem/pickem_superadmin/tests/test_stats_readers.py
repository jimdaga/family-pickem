"""Coexistence tests for global vs per-pool userStats rows.

A superadmin pool recompute (services.recompute_pool -> update_stats --pool)
writes a per-pool userStats row alongside the global (pool-null) row. Global,
all-time readers must keep reading the pool-null row and never be shadowed or
double-counted by per-pool rows.
"""
from django.test import TestCase

from pickem_api.models import Family, Pool, userStats
from pickem_homepage.templatetags.pickem_homepage_extras import lookupStats


class StatsReaderCoexistenceTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        # The global all-time row (what get_season-independent badges read).
        userStats.objects.create(
            userID='jimbo', pool=None, weeksWonSeason=7, weeksWonTotal=12,
        )
        # A per-pool row for the same user with DIFFERENT numbers.
        userStats.objects.create(
            userID='jimbo', pool=self.pool, weeksWonSeason=2, weeksWonTotal=3,
        )

    def test_lookupstats_returns_the_global_row_not_a_per_pool_row(self):
        data = lookupStats('jimbo')
        # 7 is the global figure; 2 is the per-pool figure that must not shadow it.
        self.assertEqual(data['weeksWonSeason'], 7)
        self.assertEqual(data['weeksWonTotal'], 12)
