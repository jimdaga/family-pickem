from django.apps import AppConfig


class PickemHomepageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pickem_homepage'

    def ready(self):
        # Register the user_signed_up handler that flags new accounts for the
        # username-choice gate (issue #127).
        from . import signals  # noqa: F401

        # Registers the system check that asserts the bundled email logo asset
        # is present (see email_assets._email_logo_asset_check).
        from . import email_assets  # noqa: F401
