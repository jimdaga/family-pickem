"""Re-export every view so urls.py has one import surface."""
from pickem_superadmin.views.overview import overview

__all__ = ['overview']
