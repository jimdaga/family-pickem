from django.contrib.auth.models import User
from django.test import TestCase


class SuperuserPillLinkTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.member = User.objects.create_user(
            username='member', email='member@example.com', password='pw',
        )

    def test_superuser_pill_links_to_console(self):
        self.client.force_login(self.root)
        html = self.client.get('/', follow=True).content.decode()
        self.assertIn('superuser-badge', html)
        # The badge must be wrapped in (or be) a link to the console.
        self.assertIn('href="/superadmin/"', html)

    def test_no_pill_for_ordinary_member(self):
        self.client.force_login(self.member)
        html = self.client.get('/', follow=True).content.decode()
        self.assertNotIn('superuser-badge', html)
