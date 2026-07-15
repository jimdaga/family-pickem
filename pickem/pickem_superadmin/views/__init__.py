"""Re-export every view so urls.py has one import surface."""
from pickem_superadmin.views.families import families, families_save
from pickem_superadmin.views.jobs import jobs_page, jobs_queue
from pickem_superadmin.views.overview import (
    banner_deactivate, banner_publish, overview, pool_settings_backfill, season_update,
)
from pickem_superadmin.views.pools import pools, pools_save
from pickem_superadmin.views.teams import teams, teams_save
from pickem_superadmin.views.users import user_block, user_unblock, user_update, users

__all__ = [
    'overview', 'users', 'user_block', 'user_unblock', 'user_update',
    'pools', 'pools_save',
    'families', 'families_save',
    'teams', 'teams_save',
    'jobs_page', 'jobs_queue',
    'season_update', 'pool_settings_backfill', 'banner_publish', 'banner_deactivate',
]
