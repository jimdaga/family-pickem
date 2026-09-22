from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from pickem_api.models import Notification


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", email="ana@example.com")
        self.other = User.objects.create_user(username="bo", email="bo@example.com")

    def _make(self, recipient=None, **kwargs):
        defaults = {
            "recipient": recipient or self.user,
            "kind": Notification.Kind.ANNOUNCEMENT,
            "title": "Something happened",
        }
        defaults.update(kwargs)
        return Notification.objects.create(**defaults)

    def test_new_notification_is_unread(self):
        notification = self._make()
        self.assertIsNone(notification.read_at)

    def test_default_ordering_is_newest_first(self):
        older = self._make(title="older")
        newer = self._make(title="newer")
        # created_at is auto_now_add, so force a deterministic spread rather
        # than relying on clock resolution between two same-tick inserts.
        Notification.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timezone.timedelta(hours=1)
        )
        self.assertEqual(
            [n.title for n in Notification.objects.all()], ["newer", "older"]
        )
        self.assertEqual(newer.title, "newer")

    def test_unread_for_excludes_read_rows(self):
        unread = self._make(title="unread")
        self._make(title="read", read_at=timezone.now())
        self.assertEqual([n.pk for n in Notification.objects.unread_for(self.user)], [unread.pk])

    def test_unread_for_excludes_other_users(self):
        self._make(recipient=self.other, title="not mine")
        mine = self._make(title="mine")
        self.assertEqual([n.pk for n in Notification.objects.unread_for(self.user)], [mine.pk])

    def test_recent_for_honours_limit_and_ordering(self):
        for index in range(5):
            created = self._make(title=f"n{index}")
            Notification.objects.filter(pk=created.pk).update(
                created_at=timezone.now() - timezone.timedelta(hours=5 - index)
            )
        recent = list(Notification.objects.recent_for(self.user, limit=3))
        self.assertEqual([n.title for n in recent], ["n4", "n3", "n2"])

    def test_recent_for_excludes_other_users(self):
        self._make(recipient=self.other, title="not mine")
        self._make(title="mine")
        self.assertEqual(
            [n.title for n in Notification.objects.recent_for(self.user)], ["mine"]
        )

    def test_icon_maps_every_kind(self):
        for kind in Notification.Kind:
            notification = self._make(kind=kind)
            self.assertTrue(notification.icon.startswith("fa-"))

    def test_icon_falls_back_for_unknown_kind(self):
        notification = self._make()
        notification.kind = "not_a_real_kind"
        self.assertEqual(notification.icon, Notification.DEFAULT_ICON)

    def test_mark_read_stamps_once(self):
        notification = self._make()
        notification.mark_read()
        first = notification.read_at
        self.assertIsNotNone(first)

        notification.mark_read()
        notification.refresh_from_db()
        self.assertEqual(notification.read_at, first)
