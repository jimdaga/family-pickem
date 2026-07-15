"""Re-export every view so urls.py has one import surface."""
from pickem_superadmin.views.overview import overview
from pickem_superadmin.views.pools import pools, pools_save
from pickem_superadmin.views.users import user_block, user_unblock, user_update, users

__all__ = [
    'overview', 'users', 'user_block', 'user_unblock', 'user_update',
    'pools', 'pools_save',
]
