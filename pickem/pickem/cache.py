"""Cache backend selection.

Uses Redis (shared across requests and replicas) when ``REDIS_URL`` is set,
otherwise falls back to the local file-based cache so local development and the
test suite need no external services.

See docs/superpowers/specs/2026-08-02-live-updates-design.md (Phase 1) and
issue #93.
"""


def build_caches(environ):
    """Return a Django ``CACHES`` dict based on the given environment mapping.

    ``environ`` is typically ``os.environ``. When ``REDIS_URL`` is a non-blank
    string the default cache is Redis (via django-redis); otherwise it is the
    file-based cache at ``/tmp/django_cache``.
    """
    redis_url = environ.get('REDIS_URL', '').strip()
    if redis_url:
        return {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': redis_url,
                'TIMEOUT': 300,  # 5 minutes
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                    # A cache outage must degrade to "no cache", never 500s.
                    'IGNORE_EXCEPTIONS': True,
                },
            }
        }
    return {
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': '/tmp/django_cache',
            'TIMEOUT': 300,  # 5 minutes
            'OPTIONS': {
                'MAX_ENTRIES': 1000,
            },
        }
    }
