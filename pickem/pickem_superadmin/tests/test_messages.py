from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pickem_api.models import Family, Pool
from pickem_homepage.models import MessageBoardComment, MessageBoardPost


class MessageBoardFeedTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.author = User.objects.create_user(username='grumpy', password='pw')
        self.fam_a = Family.objects.create(name='Alpha', slug='alpha')
        self.fam_b = Family.objects.create(name='Bravo', slug='bravo')
        Pool.objects.create(family=self.fam_a, name='P', slug='alpha-pool', season=2627, is_default=True)
        self.post_a = MessageBoardPost.objects.create(
            family=self.fam_a, user=self.author, title='Site is slow', content='The picks page lags',
        )
        self.post_b = MessageBoardPost.objects.create(
            family=self.fam_b, user=self.author, title='Go Bills', content='Big win',
        )
        self.comment_b = MessageBoardComment.objects.create(
            family=self.fam_b, post=self.post_b, user=self.author, content='Love this app',
        )
        self.hidden = MessageBoardComment.objects.create(
            family=self.fam_a, post=self.post_a, user=self.author, content='hidden rant', is_active=False,
        )
        # Make ordering deterministic: post_a oldest, comment_b newest.
        now = timezone.now()
        MessageBoardPost.objects.filter(pk=self.post_a.pk).update(created_at=now - timedelta(hours=3))
        MessageBoardPost.objects.filter(pk=self.post_b.pk).update(created_at=now - timedelta(hours=2))
        MessageBoardComment.objects.filter(pk=self.comment_b.pk).update(created_at=now - timedelta(hours=1))
        self.client.force_login(self.root)

    def _items(self, **params):
        response = self.client.get(reverse('superadmin:messages'), params)
        self.assertEqual(response.status_code, 200)
        return response, [(i['kind'], i['obj'].pk) for i in response.context['items']]

    def test_lists_posts_and_comments_across_families_newest_first(self):
        _response, items = self._items()
        self.assertEqual(items, [
            ('comment', self.comment_b.pk), ('post', self.post_b.pk), ('post', self.post_a.pk),
        ])

    def test_hidden_items_only_when_requested(self):
        _r, items = self._items(hidden='1')
        self.assertIn(('comment', self.hidden.pk), items)

    def test_filters_by_family_kind_and_text(self):
        self.assertEqual(self._items(family='alpha')[1], [('post', self.post_a.pk)])
        self.assertEqual(self._items(kind='comment')[1], [('comment', self.comment_b.pk)])
        self.assertEqual(self._items(q='slow')[1], [('post', self.post_a.pk)])

    def test_family_links_to_its_board_in_a_new_tab(self):
        response, _items = self._items(family='alpha')
        board = reverse('family_pool_messages', kwargs={'family_slug': 'alpha', 'pool_slug': 'alpha-pool'})
        self.assertContains(response, f'href="{board}" target="_blank" rel="noopener"')
