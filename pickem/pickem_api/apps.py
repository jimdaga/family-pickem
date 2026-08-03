import os

from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


def _should_start_scheduler(environ):
    """Start the scheduler only in the dedicated server process of the scheduler
    pod: both RUN_SCHEDULER and RUN_WEB_SERVER are the string "true".

    RUN_SCHEDULER is set at the container level (pod spec) on the scheduler
    Deployment. RUN_WEB_SERVER is NOT — it is exported only by
    docker-entrypoint.sh, at runtime, for the uvicorn server process it execs.
    So a `kubectl exec` (or management command run that way) into the
    scheduler pod inherits RUN_SCHEDULER from the pod spec but never
    RUN_WEB_SERVER, and therefore never starts a second in-process scheduler.
    Under uvicorn --workers 1 (the scheduler pod), ready() runs once.
    """
    return (
        environ.get("RUN_SCHEDULER") == "true"
        and environ.get("RUN_WEB_SERVER") == "true"
    )


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
        if not _should_start_scheduler(os.environ):
            return

        from . import scheduler

        scheduler.start()
