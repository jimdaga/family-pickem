import os

from django.apps import AppConfig


class PickemApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pickem_api'

    def ready(self):
        # Start the in-process update scheduler only where explicitly enabled.
        # See pickem_api/scheduler.py for the single-process guard rationale.
        if os.environ.get('RUN_SCHEDULER') == 'true':
            from . import scheduler
            scheduler.start()
