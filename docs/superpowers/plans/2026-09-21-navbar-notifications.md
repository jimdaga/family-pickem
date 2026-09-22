# Navbar Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold an in-app notifications system — a navbar bell with an unread badge and a dropdown panel — and trim the user's display name out of the user-dropdown trigger to make room.

**Architecture:** A new `Notification` model in `pickem_api` holds per-user rows with optional family/pool scoping and a nullable `read_at` timestamp. A context processor feeds the unread count and the ten most recent rows to every authenticated page render. `base.html` renders both a desktop dropdown (reusing the existing `toggleDropdown()` machinery) and a mobile section (reusing `toggleMobileDropdown()`). Two small views handle mark-all-read and per-item open-and-mark-read. **Nothing creates notifications yet** — producers are follow-up work.

**Tech Stack:** Django 5.2, PostgreSQL (SQLite under `pickem.test_settings`), Tailwind CSS, Font Awesome icons, Django template language.

**Spec:** `docs/superpowers/specs/2026-09-21-navbar-notifications-design.md`

## Global Constraints

- All paths below are relative to the repo root `/Users/jim/git/family-pickem`. Django commands run from `pickem/`.
- Run tests with `uv run python manage.py test <label> --settings=pickem.test_settings` from `pickem/`. The `test_settings` module uses in-memory SQLite and matches CI; the default settings hit local postgres on port 55432 and produce keepdb artifacts.
- Never append a `?v=...` cache-buster to a `{% static %}` URL (see CLAUDE.md — this has regressed twice).
- New Tailwind utility classes require `npm run build:prod` from the repo root, and the rebuilt `pickem/pickem_homepage/static/css/tailwind.css` must be committed.
- `Notification.Kind` values are exactly: `picks_open`, `picks_missed`, `week_winner`, `season_winner`, `message_reply`, `family_invite`, `announcement`.
- Do not add producers, a `/notifications/` history page, SSE wiring, or email delivery. Out of scope.
- Commit after each task with a `feat(notifications):` or `test(notifications):` prefix.

---

### Task 1: `Notification` model, manager, and migration

**Files:**
- Modify: `pickem/pickem_api/models.py` (append at end of file)
- Create: `pickem/pickem_api/migrations/0102_notification.py` (generated)
- Create: `pickem/pickem_api/tests/test_notifications.py`

**Interfaces:**
- Consumes: `User`, `Family`, `Pool`, `timezone` — all already imported at the top of `models.py`.
- Produces:
  - `Notification` model with fields `recipient`, `kind`, `title`, `body`, `url`, `family`, `pool`, `read_at`, `created_at`
  - `Notification.Kind` (`models.TextChoices`)
  - `Notification.objects.unread_for(user) -> QuerySet`
  - `Notification.objects.recent_for(user, limit=10) -> QuerySet` (sliced, newest first)
  - `Notification.icon -> str` (Font Awesome class)
  - `Notification.mark_read(when=None) -> None`

- [ ] **Step 1: Write the failing tests**

Create `pickem/pickem_api/tests/test_notifications.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_notifications --settings=pickem.test_settings
```

Expected: FAIL with `ImportError: cannot import name 'Notification' from 'pickem_api.models'`.

- [ ] **Step 3: Add the model**

Append to the end of `pickem/pickem_api/models.py`:

```python
class NotificationQuerySet(models.QuerySet):
    """Query helpers for the navbar notifications panel."""

    def unread_for(self, user):
        return self.filter(recipient=user, read_at__isnull=True)

    def recent_for(self, user, limit=10):
        # select_related('pool') because the panel may label a notification
        # with its pool; the FK is nullable so this stays a LEFT JOIN.
        return self.filter(recipient=user).select_related('pool')[:limit]


class Notification(models.Model):
    """An in-app notification shown in the navbar bell.

    Nothing creates these yet -- this is the scaffold. Producers set ``url`` to
    an already-resolved path rather than a route name, because almost every
    member-facing route needs (family_slug, pool_slug) and the producer is the
    only party that reliably holds that tenant context. Keeping the path
    pre-resolved also means the navbar never risks a NoReverseMatch mid-render.
    """

    class Kind(models.TextChoices):
        PICKS_OPEN = 'picks_open', 'Picks open'
        PICKS_MISSED = 'picks_missed', 'Missed picks'
        WEEK_WINNER = 'week_winner', 'Week winner'
        SEASON_WINNER = 'season_winner', 'Season winner'
        MESSAGE_REPLY = 'message_reply', 'Message reply'
        FAMILY_INVITE = 'family_invite', 'Family invite'
        ANNOUNCEMENT = 'announcement', 'Announcement'

    #: Font Awesome class per kind, so the template renders {{ n.icon }}
    #: instead of carrying an {% if %} ladder that has to grow with the enum.
    KIND_ICONS = {
        Kind.PICKS_OPEN: 'fa-clipboard-list',
        Kind.PICKS_MISSED: 'fa-triangle-exclamation',
        Kind.WEEK_WINNER: 'fa-trophy',
        Kind.SEASON_WINNER: 'fa-crown',
        Kind.MESSAGE_REPLY: 'fa-comment-dots',
        Kind.FAMILY_INVITE: 'fa-ticket',
        Kind.ANNOUNCEMENT: 'fa-bullhorn',
    }
    DEFAULT_ICON = 'fa-bell'

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications',
    )
    kind = models.CharField(
        max_length=32, choices=Kind.choices, default=Kind.ANNOUNCEMENT,
    )
    title = models.CharField(max_length=200, help_text="The bold line in the panel")
    body = models.CharField(
        max_length=500, blank=True, default='', help_text="Optional supporting line",
    )
    url = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Already-resolved path this notification links to",
    )

    # Nullable: account-level notifications (invites, announcements) belong to
    # no pool. SET_NULL so deleting a pool never deletes someone's history.
    family = models.ForeignKey(
        Family, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notifications',
    )
    pool = models.ForeignKey(
        Pool, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notifications',
    )

    # A nullable timestamp rather than an is_read boolean: it answers both
    # "is it read" and "when was it read" at no extra cost.
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Covers both the badge count and the recent-items list.
            models.Index(
                fields=['recipient', 'read_at', '-created_at'],
                name='notification_recipient_idx',
            ),
        ]

    def __str__(self):
        return f"{self.recipient.username}: {self.title}"

    @property
    def icon(self):
        return self.KIND_ICONS.get(self.kind, self.DEFAULT_ICON)

    def mark_read(self, when=None):
        """Stamp ``read_at`` if still unread. A no-op once read."""
        if self.read_at is None:
            self.read_at = when or timezone.now()
            self.save(update_fields=['read_at'])
```

- [ ] **Step 4: Generate the migration**

```bash
cd pickem && uv run python manage.py makemigrations pickem_api
```

Expected: creates `pickem_api/migrations/0102_notification.py`. Read the generated file and confirm it contains only `CreateModel` plus `AddIndex` — no `AlterField` on unrelated models. If unrelated operations appear, they are pre-existing model drift; stop and report rather than committing them.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd pickem && uv run python manage.py test pickem_api.tests.test_notifications --settings=pickem.test_settings
```

Expected: PASS, 9 tests.

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_api/models.py pickem/pickem_api/migrations/0102_notification.py pickem/pickem_api/tests/test_notifications.py
git commit -m "feat(notifications): add Notification model and manager"
```

---

### Task 2: Context processor

**Files:**
- Modify: `pickem/pickem/context_processors.py` (add import, append function)
- Modify: `pickem/pickem/settings.py:156-165` (register the processor)
- Modify: `pickem/pickem_homepage/tests.py` (append a test class)

**Interfaces:**
- Consumes: `Notification.objects.unread_for()`, `Notification.objects.recent_for()` from Task 1.
- Produces: template context keys `notification_unread_count` (int) and `notification_items` (list of `Notification`), available on every render.

- [ ] **Step 1: Write the failing tests**

Append to `pickem/pickem_homepage/tests.py`:

```python
class NotificationsContextProcessorTests(TestCase):
    """The navbar bell's data must be present on every authenticated render."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="notify-ana", email="notify-ana@example.com", password="pw",
        )
        self.other = User.objects.create_user(
            username="notify-bo", email="notify-bo@example.com", password="pw",
        )

    def _context(self, user):
        from pickem.context_processors import notifications_context

        request = self.factory.get("/")
        request.user = user
        return notifications_context(request)

    def test_anonymous_gets_empty_defaults(self):
        context = self._context(AnonymousUser())
        self.assertEqual(context["notification_unread_count"], 0)
        self.assertEqual(context["notification_items"], [])

    def test_counts_only_unread_for_this_user(self):
        Notification.objects.create(recipient=self.user, title="unread one")
        Notification.objects.create(recipient=self.user, title="unread two")
        Notification.objects.create(
            recipient=self.user, title="already read", read_at=timezone.now(),
        )
        Notification.objects.create(recipient=self.other, title="someone else's")

        context = self._context(self.user)

        self.assertEqual(context["notification_unread_count"], 2)
        titles = [n.title for n in context["notification_items"]]
        self.assertNotIn("someone else's", titles)
        # Read rows still appear in the list -- they just render un-highlighted.
        self.assertIn("already read", titles)

    def test_items_are_capped_at_ten(self):
        for index in range(12):
            Notification.objects.create(recipient=self.user, title=f"n{index}")
        context = self._context(self.user)
        self.assertEqual(len(context["notification_items"]), 10)

    def test_database_error_degrades_to_defaults(self):
        # A context processor that raises breaks every page on the site, so it
        # must swallow and degrade rather than propagate.
        with patch(
            "pickem.context_processors.Notification.objects.unread_for",
            side_effect=OperationalError("boom"),
        ):
            context = self._context(self.user)
        self.assertEqual(context["notification_unread_count"], 0)
        self.assertEqual(context["notification_items"], [])

    def test_processor_is_registered_in_settings(self):
        self.assertIn(
            "pickem.context_processors.notifications_context",
            settings.TEMPLATES[0]["OPTIONS"]["context_processors"],
        )
```

`RequestFactory`, `AnonymousUser`, `patch`, `OperationalError`, `settings`, `timezone`, and `User` are already imported at the top of `tests.py`. Add `Notification` to the existing `from pickem_api.models import (...)` block, keeping the list alphabetical (it goes after `GameWeeks`).

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.NotificationsContextProcessorTests --settings=pickem.test_settings
```

Expected: FAIL with `ImportError: cannot import name 'notifications_context'`.

- [ ] **Step 3: Add the context processor**

In `pickem/pickem/context_processors.py`, extend the existing `pickem_api.models` import to include `Notification`:

```python
from pickem_api.models import UserProfile, GameWeeks, GamesAndScores, GamePicks, userSeasonPoints, Notification
```

Then append at the end of the file:

```python
def notifications_context(request):
    """Inject the navbar bell's unread count and recent notifications.

    Costs two queries per authenticated render (one count, one list). Wrapped
    defensively for the same reason as theme_context: a context processor that
    raises takes down every page, so a DB hiccup must degrade to an empty bell.
    """
    empty = {'notification_unread_count': 0, 'notification_items': []}

    if not request.user.is_authenticated:
        return empty

    try:
        return {
            'notification_unread_count': Notification.objects.unread_for(request.user).count(),
            'notification_items': list(Notification.objects.recent_for(request.user)),
        }
    except Exception:
        return empty
```

- [ ] **Step 4: Register it in settings**

In `pickem/pickem/settings.py`, add to the `context_processors` list immediately after `'pickem.context_processors.footer_stats_context',`:

```python
                'pickem.context_processors.notifications_context',
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.NotificationsContextProcessorTests --settings=pickem.test_settings
```

Expected: PASS, 5 tests.

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem/context_processors.py pickem/pickem/settings.py pickem/pickem_homepage/tests.py
git commit -m "feat(notifications): expose unread count and recent items to templates"
```

---

### Task 3: Mark-all-read and open views

**Files:**
- Modify: `pickem/pickem_homepage/views.py` (add import, append two views and a helper)
- Modify: `pickem/pickem_homepage/urls.py` (append two routes before the closing `]`)
- Modify: `pickem/pickem_homepage/tests.py` (append a test class)

**Interfaces:**
- Consumes: `Notification` and `Notification.mark_read()` from Task 1.
- Produces:
  - URL name `notifications_mark_all_read` → `/notifications/mark-read/` (POST only)
  - URL name `notification_open` → `/notifications/<int:notification_id>/go/` (GET)
  - Both are referenced by the templates in Tasks 4 and 5.

- [ ] **Step 1: Write the failing tests**

Append to `pickem/pickem_homepage/tests.py`:

```python
class NotificationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="notify-view", email="notify-view@example.com", password="pw",
        )
        self.other = User.objects.create_user(
            username="notify-other", email="notify-other@example.com", password="pw",
        )
        self.client.force_login(self.user)

    def test_mark_all_read_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse("notifications_mark_all_read"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_mark_all_read_rejects_get(self):
        response = self.client.get(reverse("notifications_mark_all_read"))
        self.assertEqual(response.status_code, 405)

    def test_mark_all_read_marks_only_this_users_rows(self):
        mine = Notification.objects.create(recipient=self.user, title="mine")
        theirs = Notification.objects.create(recipient=self.other, title="theirs")

        self.client.post(reverse("notifications_mark_all_read"))

        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertIsNotNone(mine.read_at)
        self.assertIsNone(theirs.read_at)

    def test_mark_all_read_returns_to_same_host_referer(self):
        response = self.client.post(
            reverse("notifications_mark_all_read"), HTTP_REFERER="/standings/",
        )
        self.assertEqual(response["Location"], "/standings/")

    def test_mark_all_read_ignores_foreign_referer(self):
        response = self.client.post(
            reverse("notifications_mark_all_read"),
            HTTP_REFERER="https://evil.example.com/steal",
        )
        self.assertEqual(response["Location"], reverse("index"))

    def test_open_marks_read_and_redirects_to_url(self):
        notification = Notification.objects.create(
            recipient=self.user, title="go here", url="/standings/",
        )
        response = self.client.get(
            reverse("notification_open", args=[notification.id])
        )
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)
        self.assertEqual(response["Location"], "/standings/")

    def test_open_redirects_to_index_when_url_blank(self):
        notification = Notification.objects.create(recipient=self.user, title="no url")
        response = self.client.get(
            reverse("notification_open", args=[notification.id])
        )
        self.assertEqual(response["Location"], reverse("index"))

    def test_open_refuses_foreign_host_url(self):
        # A bad producer must not be able to turn a notification into an open
        # redirect off-site.
        notification = Notification.objects.create(
            recipient=self.user, title="sketchy", url="https://evil.example.com/",
        )
        response = self.client.get(
            reverse("notification_open", args=[notification.id])
        )
        self.assertEqual(response["Location"], reverse("index"))

    def test_open_404s_on_another_users_notification(self):
        notification = Notification.objects.create(
            recipient=self.other, title="not yours", url="/standings/",
        )
        response = self.client.get(
            reverse("notification_open", args=[notification.id])
        )
        # 404 rather than 403: the endpoint must not confirm the row exists.
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.NotificationViewTests --settings=pickem.test_settings
```

Expected: FAIL with `NoReverseMatch: Reverse for 'notifications_mark_all_read' not found`.

- [ ] **Step 3: Add the views**

In `pickem/pickem_homepage/views.py`, add the import (near the other `django.utils` imports around line 51):

```python
from django.utils.http import url_has_allowed_host_and_scheme
```

Add `Notification` to the existing `pickem_api.models` import line:

```python
from pickem_api.models import GamesAndScores, GameWeeks, Teams, userSeasonPoints, userStats, UserProfile, Notification
```

Append at the end of `views.py`:

```python
def _safe_internal_redirect(request, url):
    """Return ``url`` when it points back at this site, else the lobby.

    Both notification views redirect to a caller-influenced URL -- a Referer
    header in one case, a stored producer-written path in the other -- so both
    must be validated or they become open redirects.
    """
    if url and url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return url
    return reverse('index')


@login_required
@require_http_methods(["POST"])
def notifications_mark_all_read(request):
    """Clear the navbar badge by stamping every unread row for this user."""
    Notification.objects.unread_for(request.user).update(read_at=timezone.now())
    return redirect(_safe_internal_redirect(request, request.META.get('HTTP_REFERER')))


@login_required
def notification_open(request, notification_id):
    """Mark one notification read, then send the user where it points."""
    notification = get_object_or_404(
        Notification, pk=notification_id, recipient=request.user,
    )
    notification.mark_read()
    return redirect(_safe_internal_redirect(request, notification.url))
```

- [ ] **Step 4: Add the URLs**

In `pickem/pickem_homepage/urls.py`, insert immediately before the closing `]`:

```python

    # Notification URLs
    path('notifications/mark-read/', views.notifications_mark_all_read, name='notifications_mark_all_read'),
    path('notifications/<int:notification_id>/go/', views.notification_open, name='notification_open'),
```

Both paths fall outside `RequireLoginForInternalPagesMiddleware.PUBLIC_PREFIXES` / `PUBLIC_EXACT_PATHS`, so the middleware already forces login before the view's own `@login_required` is reached. That is why `test_mark_all_read_requires_login` asserts a redirect rather than a 405 — the middleware runs first.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.NotificationViewTests --settings=pickem.test_settings
```

Expected: PASS, 9 tests.

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_homepage/views.py pickem/pickem_homepage/urls.py pickem/pickem_homepage/tests.py
git commit -m "feat(notifications): add mark-all-read and open views"
```

---

### Task 4: Desktop navbar bell, panel, and user-dropdown trim

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/base.html` (insert bell block before the user dropdown at ~line 181; delete the name span at ~line 196)
- Modify: `pickem/pickem_homepage/tests.py` (append a test class)

**Interfaces:**
- Consumes: `notification_unread_count` / `notification_items` (Task 2), URL names `notifications_mark_all_read` and `notification_open` (Task 3), `Notification.icon` (Task 1).
- Produces: `data-testid="notifications-bell"`, `data-testid="notifications-badge"`, `data-testid="notifications-panel"` hooks used by the tests.

- [ ] **Step 1: Write the failing tests**

Append to `pickem/pickem_homepage/tests.py`:

```python
class NotificationNavbarTests(TestCase):
    """The bell, its badge, and the trimmed user dropdown.

    These render against ``profile`` rather than ``index``: ``index`` always
    redirects an authenticated user (to onboarding, their pool lobby, or the
    family picker), so it never returns navbar HTML to assert against.
    ``profile`` extends base.html and needs no family membership.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="notify-nav", email="notify-nav@example.com", password="pw",
        )
        self.client.force_login(self.user)

    def test_bell_renders_for_authenticated_user(self):
        response = self.client.get(reverse("profile"))
        self.assertContains(response, 'data-testid="notifications-bell"')
        self.assertContains(response, 'data-testid="notifications-panel"')

    def test_no_badge_when_nothing_unread(self):
        Notification.objects.create(
            recipient=self.user, title="read one", read_at=timezone.now(),
        )
        response = self.client.get(reverse("profile"))
        self.assertNotContains(response, 'data-testid="notifications-badge"')

    def test_badge_shows_unread_count(self):
        for index in range(3):
            Notification.objects.create(recipient=self.user, title=f"n{index}")
        response = self.client.get(reverse("profile"))
        self.assertContains(response, 'data-testid="notifications-badge"')
        self.assertContains(response, ">3<")

    def test_badge_caps_at_nine_plus(self):
        for index in range(12):
            Notification.objects.create(recipient=self.user, title=f"n{index}")
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "9+")

    def test_panel_lists_notification_titles(self):
        Notification.objects.create(
            recipient=self.user, title="You won week 3", body="Nice picks",
        )
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "You won week 3")
        self.assertContains(response, "Nice picks")

    def test_panel_shows_empty_state(self):
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "You&#x27;re all caught up.")

    def test_user_dropdown_trigger_no_longer_shows_display_name(self):
        # The name moved into the dropdown body to make room for the bell. It
        # must still appear once (in the dropdown header), just not in the
        # trigger button.
        response = self.client.get(reverse("profile"))
        html = response.content.decode()
        trigger_start = html.index('aria-label="User menu"')
        trigger_end = html.index("nav-dropdown", trigger_start)
        trigger_markup = html[trigger_start:trigger_end]
        self.assertNotIn("notify-nav", trigger_markup)
        self.assertIn("notify-nav", html[trigger_end:])
```

Note on `test_panel_shows_empty_state`: Django autoescapes the apostrophe in "You're" to `&#x27;`. If the assertion fails on the raw form, check the rendered HTML before changing the copy.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.NotificationNavbarTests --settings=pickem.test_settings
```

Expected: FAIL — `notifications-bell` not found, and the display-name test fails because the name is still in the trigger.

- [ ] **Step 3: Insert the bell block**

In `pickem/pickem_homepage/templates/pickem/base.html`, immediately **before** the `<!-- User Profile Dropdown -->` comment (~line 181), insert:

```html
                        <!-- Notifications -->
                        <div class="relative dropdown-container">
                            <button class="dropdown-trigger relative flex items-center px-3 py-2 rounded-xl border border-slate-600 hover:bg-slate-700 transition-colors"
                                    data-testid="notifications-bell"
                                    aria-label="Notifications" onclick="toggleDropdown(event, this)">
                                <i class="fas fa-bell text-white"></i>
                                {% if notification_unread_count %}
                                <span data-testid="notifications-badge"
                                      class="absolute -top-1 -right-1 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold leading-4 text-white">{% if notification_unread_count > 9 %}9+{% else %}{{ notification_unread_count }}{% endif %}</span>
                                {% endif %}
                            </button>

                            <div data-testid="notifications-panel"
                                 class="nav-dropdown absolute right-0 mt-2 w-80 bg-surface-light dark:bg-surface rounded-xl shadow-card border border-border-light dark:border-border-subtle hidden z-50 py-2">
                                <div class="flex items-center justify-between px-4 py-2">
                                    <span class="font-bold text-text-dark dark:text-white">Notifications</span>
                                    {% if notification_unread_count %}
                                    <form method="post" action="{% url 'notifications_mark_all_read' %}">
                                        {% csrf_token %}
                                        <button type="submit" class="text-xs font-semibold text-primary hover:underline">Mark all read</button>
                                    </form>
                                    {% endif %}
                                </div>
                                <div class="border-t border-border-light dark:border-border-subtle"></div>
                                <div class="max-h-96 overflow-y-auto">
                                    {% for n in notification_items %}
                                    <a href="{% url 'notification_open' n.id %}"
                                       class="flex items-start gap-3 px-4 py-3 hover:bg-border-light dark:hover:bg-surface-hover transition-colors {% if not n.read_at %}border-l-2 border-primary bg-primary/5{% endif %}">
                                        <i class="fas {{ n.icon }} mt-0.5 text-text-secondary-light dark:text-text-secondary" aria-hidden="true"></i>
                                        <span class="min-w-0">
                                            <span class="block text-sm font-semibold text-text-dark dark:text-white">{{ n.title }}</span>
                                            {% if n.body %}<span class="block text-xs text-text-secondary-light dark:text-text-secondary">{{ n.body }}</span>{% endif %}
                                            <span class="mt-0.5 block text-[11px] text-text-secondary-light dark:text-text-secondary">{{ n.created_at|timesince }} ago</span>
                                        </span>
                                    </a>
                                    {% empty %}
                                    <div class="px-4 py-6 text-center text-sm text-text-secondary-light dark:text-text-secondary">You're all caught up.</div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>
```

This reuses `.dropdown-container` / `.dropdown-trigger` / `.nav-dropdown`, so the existing `toggleDropdown()`, the click-outside-to-close handler, and the close-all-other-dropdowns behaviour all apply with no new JavaScript.

- [ ] **Step 4: Remove the display name from the user-dropdown trigger**

In the same file, delete these three lines from the user-dropdown trigger (~line 196):

```html
                                <span class="text-white font-medium">
                                    {{ user|display_name }}
                                </span>
```

Leave the avatar block, the `data-testid="navbar-rank"` pip, and the chevron untouched.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.NotificationNavbarTests --settings=pickem.test_settings
```

Expected: PASS, 7 tests.

- [ ] **Step 6: Rebuild Tailwind**

```bash
npm run build:prod
```

Run from the repo root. This is **not optional and not deferrable to Task 5**:
`pickem_homepage/tests.py:12077`
(`test_every_opacity_utility_used_in_a_template_is_compiled`) scans every
template for slash-opacity utilities and asserts each one exists in the built
`tailwind.css`. The panel markup above uses `bg-primary/5`, so Step 7 fails
until the stylesheet is regenerated.

- [ ] **Step 7: Run the full homepage suite to catch collateral damage**

```bash
cd pickem && uv run python manage.py test pickem_homepage --settings=pickem.test_settings
```

Expected: PASS. Two specific things to watch:
- If a pre-existing test asserted the display name in the navbar, update that
  assertion to look in the dropdown body rather than deleting the test.
- `test_every_opacity_utility_used_in_a_template_is_compiled` must pass. If it
  fails, Step 6 was skipped or `bg-primary/5` is outside Tailwind's opacity
  scale — in which case switch to a step that is on the scale (`/5` and `/10`
  both are) rather than suppressing the test.

- [ ] **Step 8: Commit**

```bash
git add pickem/pickem_homepage/templates/pickem/base.html pickem/pickem_homepage/static/css/tailwind.css pickem/pickem_homepage/tests.py
git commit -m "feat(notifications): add navbar bell and panel, trim name from user menu"
```

---

### Task 5: Mobile bell and menu section, plus Tailwind rebuild

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/base.html` (wrap the mobile toggle at ~line 73, add a menu section at ~line 250, add a JS handler near the `mobile-menu-btn` listener at ~line 502)
- Modify: `pickem/pickem_homepage/static/css/tailwind.css` (regenerated)
- Modify: `pickem/pickem_homepage/tests.py` (append a test class)

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: `data-testid="notifications-bell-mobile"` and `data-testid="mobile-notifications-trigger"`.

- [ ] **Step 1: Write the failing tests**

Append to `pickem/pickem_homepage/tests.py`:

```python
class NotificationMobileNavTests(TestCase):
    """Mobile bell + in-menu section. Renders against ``profile`` for the same
    reason as NotificationNavbarTests -- ``index`` always redirects."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="notify-mobile", email="notify-mobile@example.com", password="pw",
        )
        self.client.force_login(self.user)

    def test_mobile_bell_and_section_render(self):
        response = self.client.get(reverse("profile"))
        self.assertContains(response, 'data-testid="notifications-bell-mobile"')
        self.assertContains(response, 'data-testid="mobile-notifications-trigger"')

    def test_mobile_section_lists_notifications(self):
        Notification.objects.create(recipient=self.user, title="Mobile visible item")
        response = self.client.get(reverse("profile"))
        # Once in the desktop panel, once in the mobile section.
        self.assertContains(response, "Mobile visible item", count=2)

    def test_mobile_badge_hidden_when_nothing_unread(self):
        response = self.client.get(reverse("profile"))
        self.assertNotContains(response, 'data-testid="notifications-badge-mobile"')
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.NotificationMobileNavTests --settings=pickem.test_settings
```

Expected: FAIL — `notifications-bell-mobile` not found.

- [ ] **Step 3: Add the mobile bell next to the hamburger**

Replace the existing mobile toggle button block (~lines 72-80) with a flex wrapper holding both buttons:

```html
                <div class="lg:hidden flex items-center gap-1">
                    <button id="mobile-notifications-btn" type="button"
                            class="relative p-2 text-gray-300 hover:bg-slate-700 rounded-lg transition-colors"
                            data-testid="notifications-bell-mobile"
                            aria-label="Notifications">
                        <i class="fas fa-bell text-xl"></i>
                        {% if notification_unread_count %}
                        <span data-testid="notifications-badge-mobile"
                              class="absolute top-0 right-0 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold leading-4 text-white">{% if notification_unread_count > 9 %}9+{% else %}{{ notification_unread_count }}{% endif %}</span>
                        {% endif %}
                    </button>
                    <button id="mobile-menu-btn" class="p-2 text-gray-300 hover:bg-slate-700 rounded-lg transition-colors" type="button"
                            aria-controls="navbarContent"
                            aria-expanded="false"
                            aria-label="Toggle navigation">
                        <i class="fas fa-bars text-xl"></i>
                    </button>
                </div>
```

Note the `lg:hidden` moved from the `#mobile-menu-btn` element onto the new wrapper, so both buttons hide together on desktop.

- [ ] **Step 4: Add the notifications section inside the mobile menu**

In `#mobile-menu`, as the **first** child of `<div class="px-4 py-4 space-y-2">`, insert:

```html
                    <!-- Mobile Notifications -->
                    <div class="mobile-dropdown-container">
                        <button class="w-full flex items-center justify-between px-4 py-3 text-white hover:bg-slate-700 rounded-lg transition-colors mobile-dropdown-trigger"
                                data-testid="mobile-notifications-trigger"
                                onclick="toggleMobileDropdown(this)">
                            <span class="flex items-center">
                                <i class="fas fa-bell mr-3"></i>Notifications
                                {% if notification_unread_count %}
                                <span class="ml-2 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold leading-4 text-white">{% if notification_unread_count > 9 %}9+{% else %}{{ notification_unread_count }}{% endif %}</span>
                                {% endif %}
                            </span>
                            <i class="fas fa-chevron-down text-xs"></i>
                        </button>
                        <div class="mobile-dropdown-menu hidden pl-8 pr-4 py-2 space-y-1">
                            {% if notification_unread_count %}
                            <form method="post" action="{% url 'notifications_mark_all_read' %}" class="px-2 pb-1">
                                {% csrf_token %}
                                <button type="submit" class="text-xs font-semibold text-primary hover:underline">Mark all read</button>
                            </form>
                            {% endif %}
                            {% for n in notification_items %}
                            <a href="{% url 'notification_open' n.id %}"
                               class="flex items-start gap-3 px-2 py-2 rounded-lg text-white hover:bg-slate-700 transition-colors {% if not n.read_at %}border-l-2 border-primary{% endif %}">
                                <i class="fas {{ n.icon }} mt-0.5 text-slate-400" aria-hidden="true"></i>
                                <span class="min-w-0">
                                    <span class="block text-sm font-semibold">{{ n.title }}</span>
                                    {% if n.body %}<span class="block text-xs text-slate-400">{{ n.body }}</span>{% endif %}
                                    <span class="mt-0.5 block text-[11px] text-slate-400">{{ n.created_at|timesince }} ago</span>
                                </span>
                            </a>
                            {% empty %}
                            <div class="px-2 py-3 text-sm text-slate-400">You're all caught up.</div>
                            {% endfor %}
                        </div>
                    </div>
```

Place it **outside** the `{% if current_family and current_pool %}` guard that wraps the Lobby link, so notifications appear even for a user with no active pool.

- [ ] **Step 5: Wire the mobile bell to open the menu and expand the section**

In the `<script>` block, immediately after the existing `mobileMenuBtn` listener (the `if (mobileMenuBtn && mobileMenu) { ... }` block ending ~line 517), add:

```javascript
        // Mobile bell: open the menu and expand the notifications section in
        // one tap. This is the only new JS in the notifications feature --
        // everything else reuses toggleDropdown/toggleMobileDropdown.
        const mobileNotificationsBtn = document.getElementById('mobile-notifications-btn');
        if (mobileNotificationsBtn && mobileMenu) {
            mobileNotificationsBtn.addEventListener('click', function() {
                mobileMenu.classList.remove('hidden');
                if (mobileMenuBtn) {
                    mobileMenuBtn.setAttribute('aria-expanded', 'true');
                }

                const trigger = document.querySelector('[data-testid="mobile-notifications-trigger"]');
                if (!trigger) { return; }
                const section = trigger.closest('.mobile-dropdown-container')
                    .querySelector('.mobile-dropdown-menu');
                if (section && section.classList.contains('hidden')) {
                    toggleMobileDropdown(trigger);
                }
            });
        }
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd pickem && uv run python manage.py test pickem_homepage.tests.NotificationMobileNavTests --settings=pickem.test_settings
```

Expected: PASS, 3 tests.

- [ ] **Step 7: Rebuild Tailwind**

```bash
npm run build:prod
```

Run from the repo root. Task 4 already rebuilt for the desktop utilities; this picks up anything the mobile markup adds. Without it the mobile badge and section render unstyled in production, and `test_every_opacity_utility_used_in_a_template_is_compiled` (`tests.py:12077`) fails on any new slash-opacity utility.

- [ ] **Step 8: Run the full suite**

```bash
cd pickem && uv run python manage.py test --settings=pickem.test_settings
```

Expected: PASS across `pickem_api`, `pickem_homepage`, and `pickem_superadmin`.

- [ ] **Step 9: Verify in the browser**

The dev server runs at `http://localhost:8000` (do not start it yourself). Check by hand:
- The bell appears left of the avatar; the avatar no longer has a name beside it.
- With no rows, the panel shows "You're all caught up."
- Create a row from the shell, reload, and confirm the badge appears and the panel lists it:

```bash
cd pickem && uv run python manage.py shell -c "
from django.contrib.auth.models import User
from pickem_api.models import Notification
u = User.objects.get(username='<your-username>')
Notification.objects.create(recipient=u, kind=Notification.Kind.WEEK_WINNER, title='You won week 3', body='14 of 16 correct', url='/standings/')
"
```

- Click the item: it should redirect to `/standings/` and the badge should drop.
- Narrow the window below `lg` and confirm the mobile bell opens the menu with the section expanded.

- [ ] **Step 10: Commit**

```bash
git add pickem/pickem_homepage/templates/pickem/base.html pickem/pickem_homepage/static/css/tailwind.css pickem/pickem_homepage/tests.py
git commit -m "feat(notifications): add mobile bell and menu section"
```
