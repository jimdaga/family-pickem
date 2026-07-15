from django import template

register = template.Library()


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
