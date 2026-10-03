from unittest.mock import patch

from django.test import TestCase

from pickem_superadmin.templatetags.sa_extras import sa_static_v


class SaStaticVTests(TestCase):
    def test_leaves_signed_s3_urls_untouched(self):
        """Production serves static via S3 querystring-signed URLs. Appending
        ?v= would corrupt the signature and the browser would block the CSS, so
        a URL that already has a query string must be returned unchanged."""
        signed = 'https://bucket.s3.amazonaws.com/static/css/tailwind.css?X-Amz-Signature=abc123'
        with patch('pickem_superadmin.templatetags.sa_extras.static', return_value=signed):
            self.assertEqual(sa_static_v('css/tailwind.css'), signed)

    def test_appends_version_to_plain_local_urls(self):
        with patch('pickem_superadmin.templatetags.sa_extras.static', return_value='/static/css/tailwind.css'):
            result = sa_static_v('css/tailwind.css')
        # Either a ?v= cache-buster (file found on disk) or the plain URL (not
        # found) — but never a corrupted double query string.
        self.assertTrue(
            result == '/static/css/tailwind.css' or result.startswith('/static/css/tailwind.css?v='),
            result,
        )
        self.assertEqual(result.count('?'), 0 if '?' not in result else 1)


class PoolLobbyLinkTests(TestCase):
    def test_links_to_family_lobby_in_new_tab(self):
        from django.urls import reverse

        from pickem_api.models import Family, Pool
        from pickem_superadmin.templatetags.sa_extras import pool_lobby_link

        family = Family.objects.create(name='Link <Fam>', slug='link-fam')
        pool = Pool.objects.create(family=family, name='P', slug='link-pool', season=2627)

        html = pool_lobby_link(pool)

        lobby = reverse('family_pool_home', kwargs={'family_slug': 'link-fam', 'pool_slug': 'link-pool'})
        self.assertIn(f'href="{lobby}"', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('rel="noopener"', html)
        self.assertIn('>link-fam/link-pool</a>', html)
        self.assertIn('Link &lt;Fam&gt;', html)  # escaped
