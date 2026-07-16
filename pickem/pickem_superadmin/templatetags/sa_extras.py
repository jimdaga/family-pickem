import logging
import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def sa_static_v(path):
    """Static URL with a cache-busting `?v=<mtime>` suffix, for LOCAL dev only.

    The console's CSS changes often during development and is served with only a
    Last-Modified header, so browsers can hold a stale copy and render the page
    unstyled. Keying the URL to the file's mtime forces a fresh fetch.

    CRITICAL: in production this app serves static files via S3 querystring-
    signed URLs (`.../tailwind.css?X-Amz-Signature=...`). Appending `?v=` to one
    of those corrupts the signature and the browser blocks the stylesheet,
    rendering the whole console unstyled. So we only append the version when the
    generated URL has NO existing query string — i.e. the plain local-dev case.
    S3 (and any storage that hashes/signs its URLs) is returned untouched.
    """
    url = static(path)
    if '?' in url:
        return url
    absolute = finders.find(path)
    if absolute and os.path.exists(absolute):
        return f'{url}?v={int(os.path.getmtime(absolute))}'
    return url


@register.filter
def dictkey(mapping, key):
    """Look up mapping[key] in a template (Django can't index by variable key)."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def level_no(level_name):
    """Map a log level name (e.g. 'WARNING') to its numeric value for use in
    the logs console's level-filter dropdown."""
    return getattr(logging, level_name, 0)


@register.simple_tag(takes_context=True)
def sa_qs(context, **kwargs):
    """Return the current query string with the given params replaced.

    Lets a pagination link change its own page param while preserving active
    filters and the *other* table's page param. Usage: `?{% sa_qs page=3 %}`.
    A param set to None is removed.
    """
    request = context['request']
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
