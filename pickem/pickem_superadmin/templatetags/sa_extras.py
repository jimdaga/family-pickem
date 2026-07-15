import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def sa_static_v(path):
    """Static URL with a cache-busting `?v=<mtime>` suffix.

    The console's CSS changes often during development and is served with only a
    Last-Modified header, so browsers can hold a stale copy and render the page
    unstyled. Keying the URL to the file's mtime forces a fresh fetch whenever
    the file actually changes, and stays stable otherwise.
    """
    url = static(path)
    absolute = finders.find(path)
    if absolute and os.path.exists(absolute):
        return f'{url}?v={int(os.path.getmtime(absolute))}'
    return url


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
