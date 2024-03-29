from django.apps import AppConfig


class PickemApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pickem_api'

    def ready(self):
        from . import updater
        updater.start()