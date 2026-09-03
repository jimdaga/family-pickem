"""Static-ish assets that transactional emails link to.

These are served straight from the app rather than through ``{% static %}``
because in production static files live on S3 behind signed URLs with a short
TTL — by the time a recipient opens the mail the URL 403s and the image breaks.
A plain app route with a long ``Cache-Control`` never expires and is cached at
the Cloudflare edge.
"""

from pathlib import Path

from django.http import FileResponse, Http404
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

_EMAIL_LOGO_PATH = (
    Path(__file__).resolve().parent / "static" / "images" / "email-logo.png"
)

# One year, and immutable: the file only ever changes as a new deploy, and the
# path has no version query string, so treat it as permanent.
_ONE_YEAR_SECONDS = 60 * 60 * 24 * 365


@require_GET
@cache_control(public=True, max_age=_ONE_YEAR_SECONDS, immutable=True)
def email_logo(request):
    try:
        handle = _EMAIL_LOGO_PATH.open("rb")
    except FileNotFoundError as error:  # pragma: no cover - deploy packaging bug
        raise Http404("email logo asset missing") from error
    return FileResponse(handle, content_type="image/png")
