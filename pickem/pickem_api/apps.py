import os
import sys

from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class PickemApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pickem_api'

    def ready(self):
        from django.core.cache import cache

        from .models import currentSeason

        def _bust_gameseason_cache(**kwargs):
            # footer_stats_context caches get_season() for 60s (see
            # pickem/context_processors.py); a season switch (superadmin
            # overview) must take effect immediately, not after up to 60s.
            cache.delete('footer_stats:gameseason')

        post_save.connect(_bust_gameseason_cache, sender=currentSeason, weak=False)
        post_delete.connect(_bust_gameseason_cache, sender=currentSeason, weak=False)

        # Start the in-process update scheduler only where explicitly enabled.
        # Limit startup to the actual web-server child process so management
        # commands (migrate/check/shell) do not launch background jobs.
        if os.environ.get("RUN_SCHEDULER") != "true":
            return
        if os.environ.get("RUN_WEB_SERVER") != "true":
            return
        if len(sys.argv) < 2 or sys.argv[1] != "runserver":
            return
        if os.environ.get("RUN_MAIN") != "true":
            return

        from . import scheduler

        scheduler.start()
