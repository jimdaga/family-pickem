"""Signal handlers for the homepage app.

Kept intentionally small: the only handler flags brand-new signups so the
RequireUsername gate forces them to pick their own username instead of keeping
the auto-generated one allauth mints (which collides into "Jim-1", issue #127).
"""

from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from pickem_api.models import UserProfile


@receiver(user_signed_up)
def flag_new_user_for_username_choice(sender, request, user, **kwargs):
    """Mark a freshly-registered user as needing to choose a username.

    ``user_signed_up`` fires exactly once, on the account's very first login
    (social or local) — never on subsequent logins and never for users created
    directly via ``User.objects.create_user`` (tests, management commands). That
    is precisely the "new users only" boundary we want: existing accounts keep
    ``username_confirmed=True`` (the field default) and are never gated.
    """
    UserProfile.objects.update_or_create(
        user=user,
        defaults={"username_confirmed": False},
    )
