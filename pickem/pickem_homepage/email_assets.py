"""Image assets that transactional emails link to.

These are served straight from the app rather than through ``{% static %}``
because in production static files live on S3 behind signed URLs with a ~1h TTL
— by the time a recipient opens the mail the URL 403s and the image breaks. A
plain app route with a long ``Cache-Control`` stays valid, and is cacheable by
any edge/proxy in front of it.
"""

import logging
from pathlib import Path

from django.core.checks import Error, register
from django.http import FileResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)

_EMAIL_LOGO_PATH = (
    Path(__file__).resolve().parent / "static" / "images" / "email-logo.png"
)

# The URL has no version segment, so a cached copy can only be refreshed by time.
# A week keeps the fetch rare without pinning a stale logo in inbox/proxy caches
# for long after a deploy replaces it. If the logo ever needs to change fast,
# rename the route (e.g. pickem-logo-v2.png) instead of raising this.
_LOGO_CACHE_SECONDS = 60 * 60 * 24 * 7


@require_safe  # GET + HEAD — link-preview crawlers and image proxies HEAD first
@cache_control(public=True, max_age=_LOGO_CACHE_SECONDS)
def email_logo(request):
    try:
        handle = _EMAIL_LOGO_PATH.open("rb")
    except OSError as error:
        # The PNG is committed and copied into the image, so this only fires on a
        # build/packaging regression — and by now the mail is already rendered
        # with this URL baked in. Log loudly (-> Sentry) and let it 500 rather
        # than return a 404 that blends into scanner noise.
        logger.error(
            "Email logo asset unreadable at %s (%s); transactional emails are "
            "shipping a broken image.",
            _EMAIL_LOGO_PATH,
            error.__class__.__name__,
        )
        raise
    return FileResponse(handle, content_type="image/png")


@register()
def _email_logo_asset_check(app_configs, **kwargs):
    """Fail `manage.py check` (CI and container start-up) if the bundled logo is
    missing, so a broken build never goes live shipping broken email images."""
    if _EMAIL_LOGO_PATH.is_file():
        return []
    return [
        Error(
            f"Email logo asset is missing at {_EMAIL_LOGO_PATH}.",
            hint="It must be committed and copied into the image; every "
            "transactional email links to /email/pickem-logo.png.",
            id="pickem_homepage.E001",
        )
    ]
