"""Re-export every view so urls.py has one import surface."""
from pickem_superadmin.views.audit import audit
from pickem_superadmin.views.email import email_settings
from pickem_superadmin.views.families import families, families_save, family_force_delete
from pickem_superadmin.views.jobs import jobs_page, jobs_queue, jobs_schedule_save, jobs_status
from pickem_superadmin.views.logs import logs
from pickem_superadmin.views.overview import (
    banner_deactivate, banner_publish, overview, pool_settings_backfill, season_update,
)
from pickem_superadmin.views.pools import pools, pools_save
from pickem_superadmin.views.repair import (
    game_fix, pick_delete, pool_detail, pool_recompute, pool_rescore_week, season_row_reset,
)
from pickem_superadmin.views.teams import teams, teams_save
from pickem_superadmin.views.users import user_block, user_unblock, user_update, users

__all__ = [
    'overview', 'users', 'user_block', 'user_unblock', 'user_update',
    'email_settings',
    'pools', 'pools_save',
    'families', 'families_save', 'family_force_delete',
    'teams', 'teams_save',
    'jobs_page', 'jobs_queue', 'jobs_schedule_save', 'jobs_status',
    'season_update', 'pool_settings_backfill', 'banner_publish', 'banner_deactivate',
    'audit',
    'logs',
    'pool_detail', 'pool_recompute', 'pool_rescore_week',
    'pick_delete', 'season_row_reset', 'game_fix',
]
