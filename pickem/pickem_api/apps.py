import os
import sys

from django.apps import AppConfig


class PickemApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pickem_api'

    def ready(self):
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
