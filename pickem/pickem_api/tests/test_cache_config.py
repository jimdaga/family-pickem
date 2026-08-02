from django.test import SimpleTestCase

from pickem.cache import build_caches


# NOTE: wrapped in a SimpleTestCase (rather than bare module-level functions)
# because this repo's test suite runs via `manage.py test`, which uses
# unittest discovery — bare `def test_...():` functions are silently never
# collected (0 tests run). No other test module in this codebase uses the
# bare-function style. The assertions/logic below are unchanged.
class BuildCachesTests(SimpleTestCase):
    def test_uses_filebased_cache_when_no_redis_url(self):
        caches = build_caches({})
        assert caches['default']['BACKEND'] == (
            'django.core.cache.backends.filebased.FileBasedCache'
        )

    def test_uses_redis_when_redis_url_set(self):
        caches = build_caches({'REDIS_URL': 'redis://example:6379/1'})
        default = caches['default']
        assert default['BACKEND'] == 'django_redis.cache.RedisCache'
        assert default['LOCATION'] == 'redis://example:6379/1'
        # A cache outage must degrade to "no cache", never surface as a 500.
        assert default['OPTIONS']['IGNORE_EXCEPTIONS'] is True

    def test_blank_redis_url_falls_back_to_filebased(self):
        caches = build_caches({'REDIS_URL': '   '})
        assert caches['default']['BACKEND'] == (
            'django.core.cache.backends.filebased.FileBasedCache'
        )
