# Superadmin Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a superuser-only cross-family operator console at `/superadmin/` for editing pool settings across all families, blocking users site-wide, repairing broken data, and queueing pipeline runs.

**Architecture:** A new isolated Django app `pickem_superadmin` with its own URLs, standalone (non-brand) templates, a single `@superadmin_required` gate, a `SuperAdminAuditLog` model that records every write with before/after, and HTTP-free repair functions in `services.py`. Job runs are *enqueued* into the existing APScheduler `DjangoJobStore` rather than executed in the web request.

**Tech Stack:** Django 4.0.2, django-apscheduler (existing `DjangoJobStore`), Tailwind CSS (existing build), Django test framework (SQLite in-memory).

**Spec:** `docs/superpowers/specs/2026-07-13-superadmin-console-design.md`

## Global Constraints

- **Superuser only.** Gate is `request.user.is_superuser`. Never `is_staff`, never `UserProfile.is_commissioner`.
- **Authenticated non-superusers get 404**, not 403 — the console must not confirm its own existence.
- **Anonymous users get a 302 to login**, not 404. `RequireLoginForInternalPagesMiddleware` (`pickem_homepage/middleware.py:26`) redirects *every* non-public path before any view runs. This is a deliberate deviation from the spec's "anonymous → 404": a 302 is what every internal path returns anonymously, so it discloses nothing. Do **not** add `/superadmin/` to `PUBLIC_PREFIXES` to work around this — that would make the console anonymously reachable.
- **`is_superuser` is never editable from this console.** Privilege escalation stays in Django admin / shell.
- **`pick_type=against_spread` and `include_playoffs` are permanently locked**, in the widget *and* server-side. They are unimplemented downstream, not permission-gated.
- **Every write goes through `log_action()`.** No `.save()` in a view without an audit row.
- **All writes are POST + CSRF.** Destructive writes require typed confirmation.
- **Tests:** `cd pickem && python manage.py test --settings=pickem.test_settings`. Clear `/tmp/django_cache` first if the cache backend errors.
- **New Tailwind classes require `npm run build:prod` and committing `pickem/pickem_homepage/static/css/tailwind.css`.** This repo has been bitten by forgetting it.
- **Commit messages end with:** `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

## File Structure

```
pickem/pickem_superadmin/
  __init__.py
  apps.py                     PickemSuperadminConfig
  decorators.py               @superadmin_required
  models.py                   SuperAdminAuditLog
  audit.py                    log_action() — the only write path for audit rows
  services.py                 repair actions; no HTTP awareness
  jobs.py                     queue_command(), scheduler_health()
  forms.py                    PoolSettingsRowForm, FamilyRowForm, TeamRowForm, UserRowForm, BlockUserForm
  urls.py                     app_name = 'superadmin'
  migrations/
    0001_initial.py           SuperAdminAuditLog
  views/
    __init__.py               re-exports every view (urls.py imports from here)
    overview.py
    families.py
    pools.py
    users.py
    teams.py
    jobs.py
    audit.py
  templates/superadmin/
    base.html                 standalone; extends nothing
    overview.html
    families.html
    pools.html
    users.html
    teams.html
    jobs.html
    audit.html
    _matrix_table.html        shared dense-table partial
  tests/
    __init__.py
    test_auth.py              parameterized gate test across every URL
    test_audit.py
    test_users.py
    test_pools.py
    test_teams.py
    test_families.py
    test_jobs.py
    test_services.py
    test_overview.py

Modified:
  pickem/pickem/settings.py                                 add app to INSTALLED_APPS
  pickem/pickem/urls.py                                     add path('superadmin/', ...)
  pickem/pickem_api/models.py                               UserProfile block fields
  pickem/pickem_api/migrations/00XX_userprofile_block.py    new
  pickem/pickem_api/management/commands/update_standings.py add --pool
  pickem/pickem_api/management/commands/update_stats.py     add --pool
  pickem/pickem_homepage/views.py                           remove family_pool_admin_job_runs
  pickem/pickem_homepage/urls.py                            remove its route
  pickem/pickem_homepage/templates/pickem/family_admin.html remove Job Runs card
  TODO.md                                                   tick the logo_contrast_preset item
```

Note the new app uses a `tests/` package rather than the repo's single-`tests.py` convention. `pickem_homepage/tests.py` is already 7,016 lines; a security-sensitive surface deserves test files a reviewer can actually read. Django's runner discovers both.

---

### Task 1: Scaffold the app, the gate, and the base template

The deliverable is a working, superuser-gated `/superadmin/` page. Everything after this hangs off it.

**Files:**
- Create: `pickem/pickem_superadmin/__init__.py`, `apps.py`, `decorators.py`, `urls.py`, `views/__init__.py`, `views/overview.py`
- Create: `pickem/pickem_superadmin/templates/superadmin/base.html`, `overview.html`
- Create: `pickem/pickem_superadmin/tests/__init__.py`, `tests/test_auth.py`
- Modify: `pickem/pickem/settings.py:59-79` (INSTALLED_APPS)
- Modify: `pickem/pickem/urls.py:19-23` (urlpatterns)

**Interfaces:**
- Consumes: nothing.
- Produces: `superadmin_required(view_func)` decorator; URL namespace `superadmin` with names `overview`, and later `families`, `pools`, `users`, `teams`, `jobs`, `audit`. Template `superadmin/base.html` with blocks `{% block title %}`, `{% block heading %}`, `{% block content %}`.

- [ ] **Step 1: Write the failing auth test**

Create `pickem/pickem_superadmin/tests/__init__.py` (empty) and `pickem/pickem_superadmin/tests/test_auth.py`:

```python
"""The gate. If this file goes green while a view is undecorated, the console is a hole."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import Family, FamilyMembership, Pool


# Every superadmin URL. Add a row here when you add a view — test_all_urls_are_covered
# asserts this list matches the registered URLconf, so you cannot forget.
SUPERADMIN_URLS = [
    'superadmin:overview',
]


class SuperadminAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        cls.member = User.objects.create_user(
            username='member', email='member@example.com', password='pw',
        )
        cls.commissioner = User.objects.create_user(
            username='commish', email='commish@example.com', password='pw',
        )
        family = Family.objects.create(name='Dagostino', slug='dagostino')
        Pool.objects.create(
            family=family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        FamilyMembership.objects.create(
            family=family, user=cls.member, role=FamilyMembership.Role.MEMBER,
        )
        FamilyMembership.objects.create(
            family=family, user=cls.commissioner, role=FamilyMembership.Role.OWNER,
        )

    def test_anonymous_is_redirected_to_login(self):
        # RequireLoginForInternalPagesMiddleware intercepts before the view runs.
        for name in SUPERADMIN_URLS:
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn('/accounts/', response['Location'])

    def test_ordinary_member_gets_404(self):
        self.client.force_login(self.member)
        for name in SUPERADMIN_URLS:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 404)

    def test_family_commissioner_gets_404(self):
        # A commissioner governs one family. This console is global.
        self.client.force_login(self.commissioner)
        for name in SUPERADMIN_URLS:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 404)

    def test_superuser_gets_200(self):
        self.client.force_login(self.superuser)
        for name in SUPERADMIN_URLS:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_all_urls_are_covered(self):
        """A new view with no entry in SUPERADMIN_URLS fails here — so it can never
        silently skip the gate tests above."""
        from pickem_superadmin import urls as superadmin_urls

        registered = {
            f'superadmin:{p.name}'
            for p in superadmin_urls.urlpatterns
            if p.name is not None
        }
        self.assertEqual(registered, set(SUPERADMIN_URLS))
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pickem_superadmin'`.

- [ ] **Step 3: Create the app package**

`pickem/pickem_superadmin/__init__.py` — empty file.

`pickem/pickem_superadmin/apps.py`:

```python
from django.apps import AppConfig


class PickemSuperadminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pickem_superadmin'
```

`pickem/pickem_superadmin/decorators.py`:

```python
"""The single access gate for the superadmin console.

Every view in this app carries @superadmin_required. There is no ungated view.

Non-superusers get 404 rather than 403 so the console does not confirm its own
existence to a probing account. Anonymous users never reach here at all —
RequireLoginForInternalPagesMiddleware redirects them to login first, which is
what every other internal path does, so it discloses nothing.
"""
from functools import wraps

from django.http import Http404


def superadmin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            raise Http404
        return view_func(request, *args, **kwargs)

    return _wrapped
```

`pickem/pickem_superadmin/views/overview.py`:

```python
from django.shortcuts import render

from pickem_superadmin.decorators import superadmin_required


@superadmin_required
def overview(request):
    return render(request, 'superadmin/overview.html', {})
```

`pickem/pickem_superadmin/views/__init__.py`:

```python
"""Re-export every view so urls.py has one import surface."""
from pickem_superadmin.views.overview import overview

__all__ = ['overview']
```

`pickem/pickem_superadmin/urls.py`:

```python
from django.urls import path

from pickem_superadmin import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.overview, name='overview'),
]
```

- [ ] **Step 4: Write the standalone base template**

`pickem/pickem_superadmin/templates/superadmin/base.html`. Deliberately not on-brand: no site navbar, no family switcher, no theme toggle, no brand colors.

```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}superadmin{% endblock %} · pickem superadmin</title>
  <link rel="stylesheet" href="{% static 'css/tailwind.css' %}">
</head>
<body class="bg-gray-100 text-gray-900 text-[13px] font-sans antialiased">
  <header class="bg-gray-800 text-gray-100">
    <div class="flex items-center justify-between px-4 py-2">
      <span class="font-semibold tracking-tight">pickem superadmin</span>
      <span class="text-gray-400">
        <span class="font-mono">{{ request.user.username }}</span>
        <a href="/" class="ml-3 text-gray-300 hover:text-white underline">&larr; back to site</a>
      </span>
    </div>
    <nav class="flex gap-1 px-4 pb-1">
      {% url 'superadmin:overview' as u %}
      <a href="{{ u }}" class="px-2 py-1 hover:bg-gray-700 {% if request.path == u %}bg-gray-700{% endif %}">overview</a>
      {# Later tasks add: families, pools, users, teams, jobs, audit #}
    </nav>
  </header>

  <main class="p-4">
    <h1 class="mb-3 text-base font-semibold">{% block heading %}{% endblock %}</h1>
    {% if messages %}
      {% for message in messages %}
        <div class="mb-2 border-l-4 px-3 py-2
          {% if message.tags == 'error' %}border-red-600 bg-red-50 text-red-900
          {% else %}border-green-600 bg-green-50 text-green-900{% endif %}">
          {{ message }}
        </div>
      {% endfor %}
    {% endif %}
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

`pickem/pickem_superadmin/templates/superadmin/overview.html`:

```html
{% extends 'superadmin/base.html' %}
{% block title %}overview{% endblock %}
{% block heading %}Overview{% endblock %}
{% block content %}
  <p class="text-gray-600">Health, counts, and anomalies land here in Task 11.</p>
{% endblock %}
```

- [ ] **Step 5: Wire the app into settings and root URLs**

In `pickem/pickem/settings.py`, add to `INSTALLED_APPS` (after `'pickem_api.apps.PickemApiConfig',` on line 61):

```python
    'pickem_superadmin.apps.PickemSuperadminConfig',
```

In `pickem/pickem/urls.py`, add to `urlpatterns` — **before** the `pickem_homepage` catch-all include is irrelevant here (that include is prefixed `''` but its patterns are explicit), so append:

```python
    path('superadmin/', include('pickem_superadmin.urls')),
```

Resulting `urlpatterns`:

```python
urlpatterns = [
    path('', include('pickem_homepage.urls')),
    path('api/', include('pickem_api.urls')),
    path('admin/', admin.site.urls),
    path('superadmin/', include('pickem_superadmin.urls')),
]
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: PASS, 5 tests.

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_superadmin pickem/pickem/settings.py pickem/pickem/urls.py
git commit -m "$(cat <<'EOF'
feat(superadmin): scaffold superuser-gated console app

New pickem_superadmin app at /superadmin/ with a single @superadmin_required
gate (404 for non-superusers, so the console does not confirm its existence)
and a standalone non-brand base template.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: SuperAdminAuditLog + the log_action() write path

**Files:**
- Create: `pickem/pickem_superadmin/models.py`, `audit.py`, `migrations/__init__.py`, `migrations/0001_initial.py`
- Create: `pickem/pickem_superadmin/tests/test_audit.py`

**Interfaces:**
- Consumes: `superadmin_required` (Task 1).
- Produces:
  - `SuperAdminAuditLog` model with `.Action` TextChoices.
  - `log_action(request, action, target, summary, changes=None, family=None, pool=None, family_action=None) -> SuperAdminAuditLog` — the **only** way audit rows get written. `target` is a model instance (used for `target_type`/`target_id`) or `None`. When `family` is passed it also writes a `FamilyAuditLog` row using `family_action`.
  - `diff_fields(before: dict, after: dict) -> dict` returning `{field: [before, after]}` for changed fields only.

- [ ] **Step 1: Write the failing test**

`pickem/pickem_superadmin/tests/test_audit.py`:

```python
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from pickem_api.models import Family, FamilyAuditLog, Pool
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.models import SuperAdminAuditLog


class DiffFieldsTests(TestCase):
    def test_returns_only_changed_fields_as_before_after_pairs(self):
        before = {'win_points': 1, 'tie_points': 1}
        after = {'win_points': 2, 'tie_points': 1}
        self.assertEqual(diff_fields(before, after), {'win_points': [1, 2]})

    def test_returns_empty_dict_when_nothing_changed(self):
        self.assertEqual(diff_fields({'a': 1}, {'a': 1}), {})


class LogActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        cls.family = Family.objects.create(name='Dagostino', slug='dagostino')
        cls.pool = Pool.objects.create(
            family=cls.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )

    def _request(self):
        request = RequestFactory().post('/superadmin/')
        request.user = self.root
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        request.META['HTTP_USER_AGENT'] = 'pytest-agent'
        return request

    def test_writes_a_superadmin_row_with_actor_and_request_metadata(self):
        log_action(
            self._request(),
            action=SuperAdminAuditLog.Action.USER_BLOCKED,
            target=self.root,
            summary='Blocked user spammer',
            changes={'is_active': [True, False]},
        )
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.actor, self.root)
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.USER_BLOCKED)
        self.assertEqual(entry.target_type, 'User')
        self.assertEqual(entry.target_id, str(self.root.id))
        self.assertEqual(entry.changes, {'is_active': [True, False]})
        self.assertEqual(entry.ip_address, '10.0.0.5')
        self.assertEqual(entry.user_agent, 'pytest-agent')

    def test_family_scoped_action_dual_writes_to_the_family_audit_log(self):
        """A superadmin editing a pool must not leave a gap in that family's own
        history — the commissioner sees it too."""
        log_action(
            self._request(),
            action=SuperAdminAuditLog.Action.POOL_SETTINGS_UPDATED,
            target=self.pool,
            summary='Updated settings for dagostino/pickem-pool',
            changes={'win_points': [1, 2]},
            family=self.family,
            pool=self.pool,
            family_action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
        )
        self.assertEqual(SuperAdminAuditLog.objects.count(), 1)
        family_entry = FamilyAuditLog.objects.get()
        self.assertEqual(family_entry.family, self.family)
        self.assertEqual(family_entry.pool, self.pool)
        self.assertEqual(family_entry.actor, self.root)
        self.assertEqual(family_entry.metadata['changes'], {'win_points': [1, 2]})
        self.assertEqual(family_entry.metadata['source'], 'superadmin')

    def test_global_action_does_not_write_a_family_row(self):
        log_action(
            self._request(),
            action=SuperAdminAuditLog.Action.TEAM_UPDATED,
            target=None,
            summary='Updated team colors',
        )
        self.assertEqual(FamilyAuditLog.objects.count(), 0)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin.tests.test_audit --settings=pickem.test_settings
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pickem_superadmin.models'`.

- [ ] **Step 3: Write the model**

`pickem/pickem_superadmin/models.py`:

```python
from django.contrib.auth.models import User
from django.db import models


class SuperAdminAuditLog(models.Model):
    """Global audit trail for the superadmin console.

    FamilyAuditLog.family is non-null, so it structurally cannot record a global
    action (blocking a user, editing team colors, rolling the season). This table
    can. Because `changes` stores before/after, it doubles as forensics for a bad
    edit — which matters, since some repair actions are not reversible.
    """

    class Action(models.TextChoices):
        USER_BLOCKED = 'user_blocked', 'User blocked'
        USER_UNBLOCKED = 'user_unblocked', 'User unblocked'
        USER_PROFILE_UPDATED = 'user_profile_updated', 'User profile updated'
        FAMILY_UPDATED = 'family_updated', 'Family updated'
        POOL_SETTINGS_UPDATED = 'pool_settings_updated', 'Pool settings updated'
        TEAM_UPDATED = 'team_updated', 'Team updated'
        SEASON_UPDATED = 'season_updated', 'Current season updated'
        BANNER_PUBLISHED = 'banner_published', 'Site banner published'
        JOB_QUEUED = 'job_queued', 'Pipeline job queued'
        DATA_REPAIR = 'data_repair', 'Data repair action'

    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='superadmin_audit_logs',
        blank=True, null=True,
    )
    action = models.CharField(max_length=50, choices=Action.choices)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Superadmin audit log'
        verbose_name_plural = 'Superadmin audit logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='sa_audit_created_idx'),
            models.Index(fields=['action'], name='sa_audit_action_idx'),
        ]

    def __str__(self):
        return f'{self.action} by {self.actor} at {self.created_at}'
```

- [ ] **Step 4: Write the audit helper**

`pickem/pickem_superadmin/audit.py`:

```python
"""The only write path for superadmin audit rows.

Views never touch SuperAdminAuditLog.objects.create() directly. Routing every
write through log_action() is what makes "no unaudited write" enforceable rather
than aspirational.
"""
from pickem_api.models import FamilyAuditLog
from pickem_superadmin.models import SuperAdminAuditLog


def diff_fields(before, after):
    """{field: [before, after]} for changed fields only."""
    return {
        key: [before[key], after[key]]
        for key in after
        if before.get(key) != after[key]
    }


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def log_action(
    request, *, action, target, summary, changes=None,
    family=None, pool=None, family_action=None,
):
    """Record a superadmin action.

    When `family` is given, also write a FamilyAuditLog row so the family's own
    history has no gap where a superadmin acted on it. `family_action` must then
    be a FamilyAuditLog.Action value.
    """
    changes = changes or {}
    actor = request.user if request.user.is_authenticated else None

    entry = SuperAdminAuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target.__class__.__name__ if target is not None else '',
        target_id=str(target.pk) if target is not None else '',
        summary=summary,
        changes=changes,
        ip_address=_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )

    if family is not None:
        if family_action is None:
            raise ValueError('family_action is required when family is given')
        FamilyAuditLog.objects.create(
            family=family,
            pool=pool,
            actor=actor,
            action=family_action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            metadata={'source': 'superadmin', 'summary': summary, 'changes': changes},
            ip_address=entry.ip_address,
            user_agent=entry.user_agent,
        )

    return entry
```

- [ ] **Step 5: Generate the migration**

```bash
cd pickem && python manage.py makemigrations pickem_superadmin
```

Expected: `Create model SuperAdminAuditLog` → `pickem_superadmin/migrations/0001_initial.py`.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: PASS, 10 tests.

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_superadmin
git commit -m "$(cat <<'EOF'
feat(superadmin): add SuperAdminAuditLog and the log_action write path

FamilyAuditLog.family is non-null and cannot record global actions. This adds a
global audit table storing before/after diffs, plus a log_action() helper that
dual-writes a FamilyAuditLog row for family-scoped actions so a family's own
history has no gaps where a superadmin acted.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Site-wide user blocking

**Files:**
- Modify: `pickem/pickem_api/models.py` (UserProfile, after line 24 `is_commissioner`)
- Create: `pickem/pickem_api/migrations/00XX_userprofile_block_fields.py` (generated)
- Create: `pickem/pickem_superadmin/services.py`
- Create: `pickem/pickem_superadmin/tests/test_services.py`

**Interfaces:**
- Consumes: `log_action` (Task 2).
- Produces:
  - `UserProfile.blocked_at`, `.blocked_by`, `.blocked_reason`.
  - `services.block_user(request, user, reason) -> dict` — returns the `changes` diff. Raises `ValidationError` if the target is a superuser or is the actor.
  - `services.unblock_user(request, user) -> dict`.
  - `services.flush_user_sessions(user) -> int` — returns the number of sessions killed.

- [ ] **Step 1: Write the failing test**

`pickem/pickem_superadmin/tests/test_services.py`:

```python
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from pickem_api.models import UserProfile
from pickem_superadmin import services
from pickem_superadmin.models import SuperAdminAuditLog


class BlockUserTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.other_root = User.objects.create_superuser(
            username='root2', email='root2@example.com', password='pw',
        )
        self.spammer = User.objects.create_user(
            username='spammer', email='spam@example.com', password='pw',
        )
        UserProfile.objects.get_or_create(user=self.spammer)

    def _request(self):
        request = RequestFactory().post('/superadmin/users/')
        request.user = self.root
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        return request

    def test_block_deactivates_user_and_stamps_the_profile(self):
        services.block_user(self._request(), self.spammer, reason='Spamming the board')

        self.spammer.refresh_from_db()
        profile = UserProfile.objects.get(user=self.spammer)
        self.assertFalse(self.spammer.is_active)
        self.assertIsNotNone(profile.blocked_at)
        self.assertEqual(profile.blocked_by, self.root)
        self.assertEqual(profile.blocked_reason, 'Spamming the board')

    def test_block_writes_an_audit_row_with_before_after(self):
        services.block_user(self._request(), self.spammer, reason='Spamming')
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.USER_BLOCKED)
        self.assertEqual(entry.changes['is_active'], [True, False])
        self.assertEqual(entry.target_id, str(self.spammer.id))

    def test_block_flushes_the_users_existing_sessions(self):
        """Without this, a blocked user keeps browsing until their session expires."""
        self.client.force_login(self.spammer)
        self.assertEqual(Session.objects.count(), 1)

        services.block_user(self._request(), self.spammer, reason='Spamming')

        self.assertEqual(Session.objects.count(), 0)

    def test_block_leaves_other_users_sessions_alone(self):
        bystander = User.objects.create_user(username='bystander', password='pw')
        self.client.force_login(bystander)
        other_client_sessions = Session.objects.count()

        services.block_user(self._request(), self.spammer, reason='Spamming')

        self.assertEqual(Session.objects.count(), other_client_sessions)

    def test_cannot_block_a_superuser(self):
        with self.assertRaises(ValidationError):
            services.block_user(self._request(), self.other_root, reason='nope')
        self.other_root.refresh_from_db()
        self.assertTrue(self.other_root.is_active)

    def test_cannot_block_yourself(self):
        with self.assertRaises(ValidationError):
            services.block_user(self._request(), self.root, reason='nope')

    def test_failed_block_writes_no_audit_row(self):
        with self.assertRaises(ValidationError):
            services.block_user(self._request(), self.other_root, reason='nope')
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_unblock_reverses_the_block(self):
        services.block_user(self._request(), self.spammer, reason='Spamming')
        services.unblock_user(self._request(), self.spammer)

        self.spammer.refresh_from_db()
        profile = UserProfile.objects.get(user=self.spammer)
        self.assertTrue(self.spammer.is_active)
        self.assertIsNone(profile.blocked_at)
        self.assertIsNone(profile.blocked_by)
        self.assertEqual(profile.blocked_reason, '')
        self.assertEqual(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.USER_UNBLOCKED,
            ).count(),
            1,
        )
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin.tests.test_services --settings=pickem.test_settings
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pickem_superadmin.services'`.

- [ ] **Step 3: Add the UserProfile block fields**

In `pickem/pickem_api/models.py`, inside `UserProfile`, immediately after the `is_commissioner` field (line 24):

```python
    # Site-wide block. Distinct from FamilyMembership.status, which only removes a
    # user from one family. Blocking sets User.is_active = False (which Django's
    # auth backend already refuses to log in) and records who/why/when here.
    blocked_at = models.DateTimeField(
        blank=True, null=True, help_text="When this user was blocked site-wide",
    )
    blocked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='blocked_users',
        blank=True, null=True, help_text="Superadmin who blocked this user",
    )
    blocked_reason = models.TextField(
        blank=True, default='', help_text="Why this user was blocked",
    )
```

- [ ] **Step 4: Write the services**

`pickem/pickem_superadmin/services.py`:

```python
"""Repair and moderation actions.

Plain functions, no HTTP awareness beyond taking `request` for the audit trail.
That keeps them unit-testable and usable from a shell.
"""
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from pickem_api.models import UserProfile
from pickem_superadmin.audit import log_action
from pickem_superadmin.models import SuperAdminAuditLog


def flush_user_sessions(user):
    """Kill this user's active sessions so a block takes effect now, not at next
    login. Django stores the user id inside the encoded session payload, so we
    decode rather than query — the table has no user column."""
    killed = 0
    for session in Session.objects.iterator():
        data = session.get_decoded()
        if str(data.get('_auth_user_id')) == str(user.pk):
            session.delete()
            killed += 1
    return killed


@transaction.atomic
def block_user(request, user, reason):
    if user.is_superuser:
        raise ValidationError('Superusers cannot be blocked.')
    if user.pk == request.user.pk:
        raise ValidationError('You cannot block yourself.')
    if not reason or not reason.strip():
        raise ValidationError('A reason is required to block a user.')

    was_active = user.is_active
    user.is_active = False
    user.save(update_fields=['is_active'])

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.blocked_at = timezone.now()
    profile.blocked_by = request.user
    profile.blocked_reason = reason.strip()
    profile.save(update_fields=['blocked_at', 'blocked_by', 'blocked_reason'])

    flush_user_sessions(user)

    changes = {'is_active': [was_active, False], 'blocked_reason': ['', reason.strip()]}
    log_action(
        request,
        action=SuperAdminAuditLog.Action.USER_BLOCKED,
        target=user,
        summary=f'Blocked user {user.username}: {reason.strip()}',
        changes=changes,
    )
    return changes


@transaction.atomic
def unblock_user(request, user):
    was_active = user.is_active
    user.is_active = True
    user.save(update_fields=['is_active'])

    profile, _ = UserProfile.objects.get_or_create(user=user)
    previous_reason = profile.blocked_reason
    profile.blocked_at = None
    profile.blocked_by = None
    profile.blocked_reason = ''
    profile.save(update_fields=['blocked_at', 'blocked_by', 'blocked_reason'])

    changes = {'is_active': [was_active, True], 'blocked_reason': [previous_reason, '']}
    log_action(
        request,
        action=SuperAdminAuditLog.Action.USER_UNBLOCKED,
        target=user,
        summary=f'Unblocked user {user.username}',
        changes=changes,
    )
    return changes
```

- [ ] **Step 5: Generate the migration**

```bash
cd pickem && python manage.py makemigrations pickem_api
```

Expected: `Add field blocked_at/blocked_by/blocked_reason to userprofile`.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: PASS, 18 tests.

- [ ] **Step 7: Commit**

```bash
git add pickem/pickem_superadmin pickem/pickem_api/models.py pickem/pickem_api/migrations
git commit -m "$(cat <<'EOF'
feat(superadmin): add site-wide user blocking

UserProfile gains blocked_at/blocked_by/blocked_reason. block_user() deactivates
the account and flushes its live sessions so the block takes effect immediately
rather than at next login. Superusers and self cannot be blocked.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Users page

**Files:**
- Create: `pickem/pickem_superadmin/views/users.py`, `templates/superadmin/users.html`
- Create: `pickem/pickem_superadmin/tests/test_users.py`
- Modify: `pickem/pickem_superadmin/views/__init__.py`, `urls.py`, `templates/superadmin/base.html` (nav link)
- Modify: `pickem/pickem_superadmin/tests/test_auth.py` (add URLs to `SUPERADMIN_URLS`)

**Interfaces:**
- Consumes: `services.block_user`, `services.unblock_user`, `log_action`.
- Produces: URL names `superadmin:users`, `superadmin:user_block`, `superadmin:user_unblock`, `superadmin:user_update` (the last three take `<int:user_id>`).

- [ ] **Step 1: Write the failing test**

`pickem/pickem_superadmin/tests/test_users.py`:

```python
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import UserProfile
from pickem_superadmin.models import SuperAdminAuditLog


class UsersPageTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.spammer = User.objects.create_user(
            username='spammer', email='spam@example.com', password='pw',
        )
        UserProfile.objects.get_or_create(user=self.spammer)
        self.client.force_login(self.root)

    def test_page_lists_users(self):
        response = self.client.get(reverse('superadmin:users'))
        self.assertContains(response, 'spammer')

    def test_block_requires_typed_confirmation_matching_the_username(self):
        """A checkbox is too easy to click by accident. You type the username."""
        response = self.client.post(
            reverse('superadmin:user_block', args=[self.spammer.id]),
            {'confirm': 'wrong-name', 'reason': 'Spamming'},
        )
        self.spammer.refresh_from_db()
        self.assertTrue(self.spammer.is_active)
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)
        self.assertEqual(response.status_code, 302)

    def test_block_requires_a_reason(self):
        self.client.post(
            reverse('superadmin:user_block', args=[self.spammer.id]),
            {'confirm': 'spammer', 'reason': ''},
        )
        self.spammer.refresh_from_db()
        self.assertTrue(self.spammer.is_active)

    def test_block_with_correct_confirmation_blocks_the_user(self):
        self.client.post(
            reverse('superadmin:user_block', args=[self.spammer.id]),
            {'confirm': 'spammer', 'reason': 'Spamming the board'},
        )
        self.spammer.refresh_from_db()
        self.assertFalse(self.spammer.is_active)
        self.assertEqual(
            UserProfile.objects.get(user=self.spammer).blocked_reason,
            'Spamming the board',
        )

    def test_unblock_restores_the_user(self):
        self.client.post(
            reverse('superadmin:user_block', args=[self.spammer.id]),
            {'confirm': 'spammer', 'reason': 'Spamming'},
        )
        self.client.post(reverse('superadmin:user_unblock', args=[self.spammer.id]))
        self.spammer.refresh_from_db()
        self.assertTrue(self.spammer.is_active)

    def test_get_request_never_mutates(self):
        self.client.get(reverse('superadmin:user_block', args=[self.spammer.id]))
        self.spammer.refresh_from_db()
        self.assertTrue(self.spammer.is_active)

    def test_update_toggles_commissioner_and_profile_fields(self):
        self.client.post(
            reverse('superadmin:user_update', args=[self.spammer.id]),
            {
                'is_commissioner': 'on',
                'favorite_team': 'ne',
                'tagline': 'go pats',
                'private_profile': '',
                'email_notifications': 'on',
            },
        )
        profile = UserProfile.objects.get(user=self.spammer)
        self.assertTrue(profile.is_commissioner)
        self.assertEqual(profile.favorite_team, 'ne')
        self.assertEqual(profile.tagline, 'go pats')
        self.assertFalse(profile.private_profile)
        self.assertTrue(profile.email_notifications)

    def test_update_cannot_grant_superuser(self):
        """is_superuser is not in the form. A hand-crafted POST must not escalate."""
        self.client.post(
            reverse('superadmin:user_update', args=[self.spammer.id]),
            {'is_superuser': 'on', 'favorite_team': 'ne'},
        )
        self.spammer.refresh_from_db()
        self.assertFalse(self.spammer.is_superuser)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin.tests.test_users --settings=pickem.test_settings
```

Expected: FAIL — `NoReverseMatch: 'superadmin:users' is not a valid view function or pattern name`.

- [ ] **Step 3: Write the view**

`pickem/pickem_superadmin/views/users.py`:

```python
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from pickem_api.models import UserProfile
from pickem_superadmin import services
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.models import SuperAdminAuditLog

# Profile fields this console may edit. is_superuser is deliberately absent:
# granting superuser from a web form is a privilege-escalation surface.
EDITABLE_PROFILE_FIELDS = (
    'is_commissioner', 'favorite_team', 'tagline',
    'private_profile', 'email_notifications',
)
BOOLEAN_PROFILE_FIELDS = ('is_commissioner', 'private_profile', 'email_notifications')


@superadmin_required
def users(request):
    user_qs = (
        User.objects.select_related('profile')
        .annotate(family_count=Count('family_memberships', distinct=True))
        .order_by('username')
    )
    query = request.GET.get('q', '').strip()
    if query:
        user_qs = user_qs.filter(username__icontains=query)

    return render(request, 'superadmin/users.html', {
        'users': user_qs,
        'query': query,
    })


@superadmin_required
@require_POST
def user_block(request, user_id):
    target = get_object_or_404(User, pk=user_id)

    # Typed confirmation: the operator must type the username. Arming a
    # destructive action should take deliberate effort, not one stray click.
    if request.POST.get('confirm', '').strip() != target.username:
        messages.error(
            request,
            f'Confirmation did not match. Type "{target.username}" exactly to block.',
        )
        return redirect('superadmin:users')

    try:
        services.block_user(request, target, reason=request.POST.get('reason', ''))
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('superadmin:users')

    messages.success(request, f'Blocked {target.username}.')
    return redirect('superadmin:users')


@superadmin_required
@require_POST
def user_unblock(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    services.unblock_user(request, target)
    messages.success(request, f'Unblocked {target.username}.')
    return redirect('superadmin:users')


@superadmin_required
@require_POST
def user_update(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=target)

    before = {field: getattr(profile, field) for field in EDITABLE_PROFILE_FIELDS}
    for field in EDITABLE_PROFILE_FIELDS:
        if field in BOOLEAN_PROFILE_FIELDS:
            setattr(profile, field, request.POST.get(field) == 'on')
        else:
            setattr(profile, field, request.POST.get(field, '').strip())
    after = {field: getattr(profile, field) for field in EDITABLE_PROFILE_FIELDS}

    changes = diff_fields(before, after)
    if not changes:
        messages.success(request, f'No changes for {target.username}.')
        return redirect('superadmin:users')

    profile.save(update_fields=[*EDITABLE_PROFILE_FIELDS, 'updated_at'])
    log_action(
        request,
        action=SuperAdminAuditLog.Action.USER_PROFILE_UPDATED,
        target=target,
        summary=f'Updated profile for {target.username}',
        changes=changes,
    )
    messages.success(request, f'Updated {target.username}.')
    return redirect('superadmin:users')
```

- [ ] **Step 4: Write the template**

`pickem/pickem_superadmin/templates/superadmin/users.html`:

```html
{% extends 'superadmin/base.html' %}
{% block title %}users{% endblock %}
{% block heading %}Users <span class="font-normal text-gray-500">({{ users|length }})</span>{% endblock %}
{% block content %}
  <form method="get" class="mb-3">
    <input type="search" name="q" value="{{ query }}" placeholder="filter by username"
           class="border border-gray-300 px-2 py-1 w-64">
    <button type="submit" class="border border-gray-400 bg-white px-2 py-1 hover:bg-gray-50">filter</button>
  </form>

  <div class="overflow-x-auto border border-gray-300 bg-white">
    <table class="w-full border-collapse">
      <thead class="bg-gray-200 text-left">
        <tr>
          <th class="px-2 py-1 font-semibold">username</th>
          <th class="px-2 py-1 font-semibold">email</th>
          <th class="px-2 py-1 font-semibold">families</th>
          <th class="px-2 py-1 font-semibold">last login</th>
          <th class="px-2 py-1 font-semibold">status</th>
          <th class="px-2 py-1 font-semibold">profile</th>
          <th class="px-2 py-1 font-semibold">actions</th>
        </tr>
      </thead>
      <tbody>
        {% for u in users %}
          <tr class="border-t border-gray-200 align-top {% if not u.is_active %}bg-red-50{% endif %}">
            <td class="px-2 py-1 font-mono">{{ u.username }}{% if u.is_superuser %} <span class="text-purple-700">★</span>{% endif %}</td>
            <td class="px-2 py-1 text-gray-600">{{ u.email }}</td>
            <td class="px-2 py-1 font-mono">{{ u.family_count }}</td>
            <td class="px-2 py-1 text-gray-600">{{ u.last_login|date:"Y-m-d H:i"|default:"never" }}</td>
            <td class="px-2 py-1">
              {% if u.is_active %}
                <span class="text-green-700">active</span>
              {% else %}
                <span class="text-red-700 font-semibold">BLOCKED</span>
                <div class="text-gray-600">{{ u.profile.blocked_reason }}</div>
                <div class="text-gray-500">by {{ u.profile.blocked_by.username }} {{ u.profile.blocked_at|date:"Y-m-d" }}</div>
              {% endif %}
            </td>
            <td class="px-2 py-1">
              <form method="post" action="{% url 'superadmin:user_update' u.id %}" class="flex flex-wrap items-center gap-1">
                {% csrf_token %}
                <label class="flex items-center gap-1" title="commissioner">
                  <input type="checkbox" name="is_commissioner" {% if u.profile.is_commissioner %}checked{% endif %}> comm
                </label>
                <label class="flex items-center gap-1" title="private profile">
                  <input type="checkbox" name="private_profile" {% if u.profile.private_profile %}checked{% endif %}> priv
                </label>
                <label class="flex items-center gap-1" title="email notifications">
                  <input type="checkbox" name="email_notifications" {% if u.profile.email_notifications %}checked{% endif %}> email
                </label>
                <input type="text" name="favorite_team" value="{{ u.profile.favorite_team|default:'' }}"
                       placeholder="team" class="w-16 border border-gray-300 px-1">
                <input type="text" name="tagline" value="{{ u.profile.tagline|default:'' }}"
                       placeholder="tagline" class="w-32 border border-gray-300 px-1">
                <button type="submit" class="border border-gray-400 bg-white px-2 hover:bg-gray-50">save</button>
              </form>
            </td>
            <td class="px-2 py-1">
              {% if u.is_superuser %}
                <span class="text-gray-500">—</span>
              {% elif u.is_active %}
                <form method="post" action="{% url 'superadmin:user_block' u.id %}" class="flex flex-wrap items-center gap-1">
                  {% csrf_token %}
                  <input type="text" name="reason" placeholder="reason (required)"
                         class="w-40 border border-gray-300 px-1" required>
                  <input type="text" name="confirm" placeholder="type &quot;{{ u.username }}&quot;"
                         class="w-40 border border-red-400 px-1" required>
                  <button type="submit" class="border border-red-600 bg-red-600 px-2 text-white hover:bg-red-700">block</button>
                </form>
              {% else %}
                <form method="post" action="{% url 'superadmin:user_unblock' u.id %}">
                  {% csrf_token %}
                  <button type="submit" class="border border-gray-400 bg-white px-2 hover:bg-gray-50">unblock</button>
                </form>
              {% endif %}
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
{% endblock %}
```

- [ ] **Step 5: Wire the URLs, views export, nav, and auth test**

`pickem/pickem_superadmin/views/__init__.py`:

```python
"""Re-export every view so urls.py has one import surface."""
from pickem_superadmin.views.overview import overview
from pickem_superadmin.views.users import user_block, user_unblock, user_update, users

__all__ = ['overview', 'users', 'user_block', 'user_unblock', 'user_update']
```

`pickem/pickem_superadmin/urls.py`:

```python
from django.urls import path

from pickem_superadmin import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('users/', views.users, name='users'),
    path('users/<int:user_id>/block/', views.user_block, name='user_block'),
    path('users/<int:user_id>/unblock/', views.user_unblock, name='user_unblock'),
    path('users/<int:user_id>/update/', views.user_update, name='user_update'),
]
```

In `templates/superadmin/base.html`, replace the `{# Later tasks add: ... #}` comment in `<nav>` with:

```html
      {% url 'superadmin:users' as u_users %}
      <a href="{{ u_users }}" class="px-2 py-1 hover:bg-gray-700 {% if request.path == u_users %}bg-gray-700{% endif %}">users</a>
```

In `tests/test_auth.py`, the POST-only URLs need arguments and must not be GET-tested for 200, so change `SUPERADMIN_URLS` to only list GET pages, and add a separate list for the write endpoints:

```python
SUPERADMIN_URLS = [
    'superadmin:overview',
    'superadmin:users',
]

# POST-only endpoints. The gate test hits them with POST and asserts the same
# 404-for-non-superusers rule; they are excluded from the GET-200 test.
SUPERADMIN_POST_URLS = [
    ('superadmin:user_block', [1]),
    ('superadmin:user_unblock', [1]),
    ('superadmin:user_update', [1]),
]
```

Then add to `SuperadminAccessTests`:

```python
    def test_post_endpoints_reject_non_superusers(self):
        self.client.force_login(self.member)
        for name, args in SUPERADMIN_POST_URLS:
            with self.subTest(url=name):
                response = self.client.post(reverse(name, args=args))
                self.assertEqual(response.status_code, 404)
```

And update `test_all_urls_are_covered` to account for both lists:

```python
    def test_all_urls_are_covered(self):
        """A new view with no entry in these lists fails here — so it can never
        silently skip the gate tests above."""
        from pickem_superadmin import urls as superadmin_urls

        registered = {
            f'superadmin:{p.name}'
            for p in superadmin_urls.urlpatterns
            if p.name is not None
        }
        covered = set(SUPERADMIN_URLS) | {name for name, _ in SUPERADMIN_POST_URLS}
        self.assertEqual(registered, covered)
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: PASS, 27 tests.

- [ ] **Step 7: Rebuild Tailwind and commit**

```bash
npm run build:prod
git add pickem/pickem_superadmin pickem/pickem_homepage/static/css/tailwind.css
git commit -m "$(cat <<'EOF'
feat(superadmin): add users page with site-wide block/unblock

Global user table with block (typed username confirmation + required reason),
unblock, commissioner toggle, and profile field edits. is_superuser is absent
from the form and cannot be granted by a hand-crafted POST.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Pools settings matrix

The centerpiece. One dense table, every pool across every family, all 16 `PoolSettings` fields inline-editable, with optimistic-concurrency protection and server-side rejection of the locked fields.

**Files:**
- Create: `pickem/pickem_superadmin/forms.py`, `views/pools.py`, `templates/superadmin/pools.html`
- Create: `pickem/pickem_superadmin/tests/test_pools.py`
- Modify: `pickem/pickem_superadmin/views/__init__.py`, `urls.py`, `templates/superadmin/base.html`, `tests/test_auth.py`

**Interfaces:**
- Consumes: `log_action`, `diff_fields`.
- Produces: URL names `superadmin:pools` (GET) and `superadmin:pools_save` (POST). `forms.PoolSettingsRowForm` — a ModelForm over `PoolSettings` excluding `pool`, with `pick_type` and `include_playoffs` disabled.

- [ ] **Step 1: Write the failing test**

`pickem/pickem_superadmin/tests/test_pools.py`:

```python
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import Family, FamilyAuditLog, Pool, PoolSettings
from pickem_superadmin.models import SuperAdminAuditLog


class PoolsMatrixTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        self.settings = PoolSettings.objects.create(pool=self.pool)
        self.client.force_login(self.root)

    def _row(self, **overrides):
        """A full matrix row post payload for self.pool."""
        payload = {
            f'{self.pool.id}-win_points': '1',
            f'{self.pool.id}-tie_points': '1',
            f'{self.pool.id}-weekly_winner_points': '2',
            f'{self.pool.id}-primary_tiebreaker': PoolSettings.PrimaryTiebreaker.TOTAL_SCORE,
            f'{self.pool.id}-secondary_tiebreaker': PoolSettings.SecondaryTiebreaker.COMBINED_YARDS,
            f'{self.pool.id}-perfect_week_bonus_amount': '0',
            f'{self.pool.id}-entry_fee_amount': '0',
            f'{self.pool.id}-missed_pick_policy': PoolSettings.MissedPickPolicy.ZERO_POINTS,
            f'{self.pool.id}-late_join_policy': PoolSettings.LateJoinPolicy.OPEN,
            f'{self.pool.id}-payout_structure': PoolSettings.PayoutStructure.WINNER_TAKES_ALL,
            f'{self.pool.id}-updated_at': self.settings.updated_at.isoformat(),
        }
        payload.update({f'{self.pool.id}-{k}': v for k, v in overrides.items()})
        return payload

    def test_page_lists_every_pool_across_families(self):
        response = self.client.get(reverse('superadmin:pools'))
        self.assertContains(response, 'dagostino')
        self.assertContains(response, 'pickem-pool')

    def test_save_writes_only_changed_fields(self):
        self.client.post(reverse('superadmin:pools_save'), self._row(win_points='3'))
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.win_points, 3)

        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.POOL_SETTINGS_UPDATED)
        self.assertEqual(entry.changes, {'win_points': [1, 3]})

    def test_save_dual_writes_to_the_family_audit_log(self):
        self.client.post(reverse('superadmin:pools_save'), self._row(win_points='3'))
        family_entry = FamilyAuditLog.objects.get()
        self.assertEqual(family_entry.family, self.family)
        self.assertEqual(family_entry.metadata['source'], 'superadmin')

    def test_unchanged_row_writes_no_audit_entry(self):
        self.client.post(reverse('superadmin:pools_save'), self._row())
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_against_spread_is_rejected_server_side(self):
        """The widget is disabled, but never trust the widget. Enabling this would
        silently corrupt scoring — the backend does not implement it."""
        self.client.post(
            reverse('superadmin:pools_save'),
            self._row(pick_type=PoolSettings.PickType.AGAINST_SPREAD),
        )
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.pick_type, PoolSettings.PickType.STRAIGHT_UP)

    def test_include_playoffs_is_rejected_server_side(self):
        self.client.post(reverse('superadmin:pools_save'), self._row(include_playoffs='on'))
        self.settings.refresh_from_db()
        self.assertFalse(self.settings.include_playoffs)

    def test_stale_row_is_rejected_instead_of_clobbering(self):
        """Two operators with the page open must not silently overwrite each other."""
        stale = self.settings.updated_at.isoformat()
        self.client.post(reverse('superadmin:pools_save'), self._row(win_points='3'))

        response = self.client.post(
            reverse('superadmin:pools_save'),
            self._row(win_points='9', updated_at=stale),
            follow=True,
        )
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.win_points, 3)
        self.assertContains(response, 'changed since you loaded it')

    def test_invalid_cell_does_not_discard_the_valid_edits(self):
        other_pool = Pool.objects.create(
            family=self.family, name='Second', slug='second', season=2627,
        )
        other_settings = PoolSettings.objects.create(pool=other_pool)

        payload = self._row(win_points='not-a-number')
        payload.update({
            f'{other_pool.id}-win_points': '5',
            f'{other_pool.id}-tie_points': '1',
            f'{other_pool.id}-weekly_winner_points': '2',
            f'{other_pool.id}-primary_tiebreaker': PoolSettings.PrimaryTiebreaker.TOTAL_SCORE,
            f'{other_pool.id}-secondary_tiebreaker': PoolSettings.SecondaryTiebreaker.COMBINED_YARDS,
            f'{other_pool.id}-perfect_week_bonus_amount': '0',
            f'{other_pool.id}-entry_fee_amount': '0',
            f'{other_pool.id}-missed_pick_policy': PoolSettings.MissedPickPolicy.ZERO_POINTS,
            f'{other_pool.id}-late_join_policy': PoolSettings.LateJoinPolicy.OPEN,
            f'{other_pool.id}-payout_structure': PoolSettings.PayoutStructure.WINNER_TAKES_ALL,
            f'{other_pool.id}-updated_at': other_settings.updated_at.isoformat(),
        })

        response = self.client.post(reverse('superadmin:pools_save'), payload, follow=True)

        other_settings.refresh_from_db()
        self.settings.refresh_from_db()
        self.assertEqual(other_settings.win_points, 5)   # good edit landed
        self.assertEqual(self.settings.win_points, 1)    # bad edit did not
        self.assertContains(response, 'could not be saved')
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin.tests.test_pools --settings=pickem.test_settings
```

Expected: FAIL — `NoReverseMatch: 'superadmin:pools'`.

- [ ] **Step 3: Write the form**

`pickem/pickem_superadmin/forms.py`:

```python
from django import forms

from pickem_api.models import PoolSettings

CELL = 'border border-gray-300 px-1 py-0.5 w-full'
NUM_CELL = 'border border-gray-300 px-1 py-0.5 w-14 font-mono'

# Not permission-gated — unimplemented. Playoff scoring needs schema work
# (userSeasonPoints only has week_1..18) and against-the-spread has no scoring
# logic. Flipping either would silently corrupt scoring rather than enable a
# feature, so they are locked here exactly as they are in FamilyAdminSettingsForm.
LOCKED_FIELDS = ('pick_type', 'include_playoffs')


class PoolSettingsRowForm(forms.ModelForm):
    """One row of the settings matrix. Prefixed by pool id so many bind at once."""

    class Meta:
        model = PoolSettings
        fields = (
            'win_points', 'tie_points', 'weekly_winner_points',
            'picks_lock_at_kickoff', 'allow_tiebreaker',
            'primary_tiebreaker', 'secondary_tiebreaker',
            'perfect_week_bonus_enabled', 'perfect_week_bonus_amount',
            'entry_fee_enabled', 'entry_fee_amount',
            'missed_pick_policy', 'late_join_policy', 'payout_structure',
            'pick_type', 'include_playoffs',
        )
        widgets = {
            'win_points': forms.NumberInput(attrs={'class': NUM_CELL}),
            'tie_points': forms.NumberInput(attrs={'class': NUM_CELL}),
            'weekly_winner_points': forms.NumberInput(attrs={'class': NUM_CELL}),
            'perfect_week_bonus_amount': forms.NumberInput(attrs={'class': NUM_CELL}),
            'entry_fee_amount': forms.NumberInput(attrs={'class': NUM_CELL}),
            'primary_tiebreaker': forms.Select(attrs={'class': CELL}),
            'secondary_tiebreaker': forms.Select(attrs={'class': CELL}),
            'missed_pick_policy': forms.Select(attrs={'class': CELL}),
            'late_join_policy': forms.Select(attrs={'class': CELL}),
            'payout_structure': forms.Select(attrs={'class': CELL}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Django ignores submitted data for disabled fields and falls back to the
        # initial value, which defeats a hand-crafted POST. This is the server-side
        # rejection, not just a greyed-out widget.
        for name in LOCKED_FIELDS:
            self.fields[name].disabled = True
            self.fields[name].help_text = 'Not implemented yet.'
```

- [ ] **Step 4: Write the view**

`pickem/pickem_superadmin/views/pools.py`:

```python
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from pickem_api.models import FamilyAuditLog, Pool, PoolSettings
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.forms import PoolSettingsRowForm
from pickem_superadmin.models import SuperAdminAuditLog

TRACKED_FIELDS = tuple(PoolSettingsRowForm.Meta.fields)


def _pool_queryset(request):
    pools = (
        Pool.objects.select_related('family', 'settings').order_by('family__name', 'name')
    )
    family_slug = request.GET.get('family', '').strip()
    season = request.GET.get('season', '').strip()
    if family_slug:
        pools = pools.filter(family__slug=family_slug)
    if season:
        pools = pools.filter(season=season)
    return pools


@superadmin_required
def pools(request):
    rows = []
    for pool in _pool_queryset(request):
        settings_obj = getattr(pool, 'settings', None)
        rows.append({
            'pool': pool,
            'settings': settings_obj,
            # A pool with no settings row cannot be edited here; Overview links to
            # the backfill repair action instead of silently rendering blanks.
            'form': (
                PoolSettingsRowForm(instance=settings_obj, prefix=str(pool.id))
                if settings_obj else None
            ),
        })

    return render(request, 'superadmin/pools.html', {
        'rows': rows,
        'family_filter': request.GET.get('family', ''),
        'season_filter': request.GET.get('season', ''),
    })


@superadmin_required
@require_POST
def pools_save(request):
    saved, failed, stale = 0, [], []

    for pool in Pool.objects.select_related('family', 'settings'):
        prefix = str(pool.id)
        if f'{prefix}-win_points' not in request.POST:
            continue  # row not on the submitted page (filtered out)

        settings_obj = getattr(pool, 'settings', None)
        if settings_obj is None:
            continue

        # Optimistic concurrency: the row carries the updated_at it was rendered
        # with. If the DB moved on, someone else saved while this page was open.
        submitted_stamp = request.POST.get(f'{prefix}-updated_at', '')
        if submitted_stamp != settings_obj.updated_at.isoformat():
            stale.append(f'{pool.family.slug}/{pool.slug}')
            continue

        before = {f: getattr(settings_obj, f) for f in TRACKED_FIELDS}
        form = PoolSettingsRowForm(request.POST, instance=settings_obj, prefix=prefix)
        if not form.is_valid():
            failed.append(f'{pool.family.slug}/{pool.slug}')
            continue

        after = {f: form.cleaned_data[f] for f in TRACKED_FIELDS}
        changes = diff_fields(before, after)
        if not changes:
            continue

        with transaction.atomic():
            form.save()
            log_action(
                request,
                action=SuperAdminAuditLog.Action.POOL_SETTINGS_UPDATED,
                target=pool,
                summary=f'Updated settings for {pool.family.slug}/{pool.slug}',
                changes=changes,
                family=pool.family,
                pool=pool,
                family_action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
            )
        saved += 1

    if saved:
        messages.success(request, f'Saved {saved} pool(s).')
    if stale:
        messages.error(
            request,
            f'Not saved — changed since you loaded it: {", ".join(stale)}. Reload and retry.',
        )
    if failed:
        messages.error(request, f'Invalid values could not be saved: {", ".join(failed)}.')
    if not saved and not stale and not failed:
        messages.success(request, 'No changes.')

    return redirect('superadmin:pools')
```

- [ ] **Step 5: Write the template**

`pickem/pickem_superadmin/templates/superadmin/pools.html`:

```html
{% extends 'superadmin/base.html' %}
{% block title %}pools{% endblock %}
{% block heading %}Pool settings <span class="font-normal text-gray-500">({{ rows|length }})</span>{% endblock %}
{% block content %}
  <form method="get" class="mb-3 flex gap-2">
    <input type="text" name="family" value="{{ family_filter }}" placeholder="family slug"
           class="border border-gray-300 px-2 py-1">
    <input type="text" name="season" value="{{ season_filter }}" placeholder="season (e.g. 2627)"
           class="border border-gray-300 px-2 py-1 font-mono">
    <button type="submit" class="border border-gray-400 bg-white px-2 py-1 hover:bg-gray-50">filter</button>
  </form>

  <form method="post" action="{% url 'superadmin:pools_save' %}">
    {% csrf_token %}
    <div class="overflow-x-auto border border-gray-300 bg-white">
      <table class="border-collapse whitespace-nowrap">
        <thead class="bg-gray-200 text-left">
          <tr>
            <th class="sticky left-0 z-10 bg-gray-200 px-2 py-1 font-semibold">family / pool</th>
            <th class="px-2 py-1 font-semibold">season</th>
            <th class="px-2 py-1 font-semibold">win</th>
            <th class="px-2 py-1 font-semibold">tie</th>
            <th class="px-2 py-1 font-semibold">wk win</th>
            <th class="px-2 py-1 font-semibold">lock@KO</th>
            <th class="px-2 py-1 font-semibold">tiebrk</th>
            <th class="px-2 py-1 font-semibold">primary tiebrk</th>
            <th class="px-2 py-1 font-semibold">secondary tiebrk</th>
            <th class="px-2 py-1 font-semibold">perfect wk</th>
            <th class="px-2 py-1 font-semibold">bonus</th>
            <th class="px-2 py-1 font-semibold">fee?</th>
            <th class="px-2 py-1 font-semibold">fee</th>
            <th class="px-2 py-1 font-semibold">missed pick</th>
            <th class="px-2 py-1 font-semibold">late join</th>
            <th class="px-2 py-1 font-semibold">payout</th>
            <th class="px-2 py-1 font-semibold text-gray-500">pick type 🔒</th>
            <th class="px-2 py-1 font-semibold text-gray-500">playoffs 🔒</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
            <tr class="border-t border-gray-200">
              <td class="sticky left-0 z-10 border-r border-gray-200 bg-white px-2 py-1 font-mono">
                {{ row.pool.family.slug }}/{{ row.pool.slug }}
              </td>
              <td class="px-2 py-1 font-mono">{{ row.pool.season }}</td>
              {% if row.form %}
                <input type="hidden" name="{{ row.pool.id }}-updated_at"
                       value="{{ row.settings.updated_at.isoformat }}">
                <td class="px-2 py-1">{{ row.form.win_points }}</td>
                <td class="px-2 py-1">{{ row.form.tie_points }}</td>
                <td class="px-2 py-1">{{ row.form.weekly_winner_points }}</td>
                <td class="px-2 py-1 text-center">{{ row.form.picks_lock_at_kickoff }}</td>
                <td class="px-2 py-1 text-center">{{ row.form.allow_tiebreaker }}</td>
                <td class="px-2 py-1">{{ row.form.primary_tiebreaker }}</td>
                <td class="px-2 py-1">{{ row.form.secondary_tiebreaker }}</td>
                <td class="px-2 py-1 text-center">{{ row.form.perfect_week_bonus_enabled }}</td>
                <td class="px-2 py-1">{{ row.form.perfect_week_bonus_amount }}</td>
                <td class="px-2 py-1 text-center">{{ row.form.entry_fee_enabled }}</td>
                <td class="px-2 py-1">{{ row.form.entry_fee_amount }}</td>
                <td class="px-2 py-1">{{ row.form.missed_pick_policy }}</td>
                <td class="px-2 py-1">{{ row.form.late_join_policy }}</td>
                <td class="px-2 py-1">{{ row.form.payout_structure }}</td>
                <td class="bg-gray-100 px-2 py-1" title="Not implemented yet.">{{ row.form.pick_type }}</td>
                <td class="bg-gray-100 px-2 py-1 text-center" title="Not implemented yet.">{{ row.form.include_playoffs }}</td>
              {% else %}
                <td colspan="16" class="bg-yellow-50 px-2 py-1 text-yellow-900">
                  no PoolSettings row — backfill it from Overview
                </td>
              {% endif %}
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    <button type="submit" class="mt-3 border border-gray-800 bg-gray-800 px-3 py-1 text-white hover:bg-gray-700">
      Save changes
    </button>
  </form>
{% endblock %}
```

- [ ] **Step 6: Wire URLs, views export, nav, auth test**

Add to `views/__init__.py`: `from pickem_superadmin.views.pools import pools, pools_save` and extend `__all__`.

Add to `urls.py`:

```python
    path('pools/', views.pools, name='pools'),
    path('pools/save/', views.pools_save, name='pools_save'),
```

Add to `base.html` nav (same pattern as users):

```html
      {% url 'superadmin:pools' as u_pools %}
      <a href="{{ u_pools }}" class="px-2 py-1 hover:bg-gray-700 {% if request.path == u_pools %}bg-gray-700{% endif %}">pools</a>
```

In `tests/test_auth.py`: add `'superadmin:pools'` to `SUPERADMIN_URLS` and `('superadmin:pools_save', [])` to `SUPERADMIN_POST_URLS`.

- [ ] **Step 7: Run the tests to verify they pass**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: PASS, 36 tests.

- [ ] **Step 8: Rebuild Tailwind and commit**

```bash
npm run build:prod
git add pickem/pickem_superadmin pickem/pickem_homepage/static/css/tailwind.css
git commit -m "$(cat <<'EOF'
feat(superadmin): add cross-family pool settings matrix

Dense editable table of all 16 PoolSettings fields across every pool, with
optimistic-concurrency rejection of stale rows, per-cell validation that
preserves valid edits, and dual audit writes. pick_type=against_spread and
include_playoffs are rejected server-side, not merely disabled in the widget.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Families page

**Files:**
- Create: `pickem/pickem_superadmin/views/families.py`, `templates/superadmin/families.html`, `tests/test_families.py`
- Modify: `pickem/pickem_superadmin/forms.py`, `views/__init__.py`, `urls.py`, `base.html`, `tests/test_auth.py`

**Interfaces:**
- Consumes: `log_action`, `diff_fields`.
- Produces: URL names `superadmin:families` (GET), `superadmin:families_save` (POST). `forms.FamilyRowForm` — ModelForm over `Family` with fields `name`, `slug`, `logo_url`, `status`.

- [ ] **Step 1: Write the failing test**

`pickem/pickem_superadmin/tests/test_families.py`:

```python
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import Family, FamilyMembership, Pool
from pickem_superadmin.models import SuperAdminAuditLog


class FamiliesPageTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.member = User.objects.create_user(username='member', password='pw')
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        FamilyMembership.objects.create(
            family=self.family, user=self.member, role=FamilyMembership.Role.MEMBER,
        )
        self.client.force_login(self.root)

    def _row(self, **overrides):
        payload = {
            f'{self.family.id}-name': 'Dagostino',
            f'{self.family.id}-slug': 'dagostino',
            f'{self.family.id}-logo_url': '',
            f'{self.family.id}-status': Family.Status.ACTIVE,
            f'{self.family.id}-updated_at': self.family.updated_at.isoformat(),
        }
        payload.update({f'{self.family.id}-{k}': v for k, v in overrides.items()})
        return payload

    def test_page_lists_families_with_member_and_pool_counts(self):
        response = self.client.get(reverse('superadmin:families'))
        self.assertContains(response, 'dagostino')

    def test_deactivating_a_family_saves_and_audits(self):
        self.client.post(
            reverse('superadmin:families_save'),
            self._row(status=Family.Status.INACTIVE),
        )
        self.family.refresh_from_db()
        self.assertEqual(self.family.status, Family.Status.INACTIVE)

        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.FAMILY_UPDATED)
        self.assertEqual(entry.changes['status'], ['active', 'inactive'])

    def test_unchanged_row_writes_no_audit_entry(self):
        self.client.post(reverse('superadmin:families_save'), self._row())
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_stale_row_is_rejected(self):
        stale = self.family.updated_at.isoformat()
        self.client.post(reverse('superadmin:families_save'), self._row(name='First'))
        response = self.client.post(
            reverse('superadmin:families_save'),
            self._row(name='Second', updated_at=stale),
            follow=True,
        )
        self.family.refresh_from_db()
        self.assertEqual(self.family.name, 'First')
        self.assertContains(response, 'changed since you loaded it')
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin.tests.test_families --settings=pickem.test_settings
```

Expected: FAIL — `NoReverseMatch: 'superadmin:families'`.

- [ ] **Step 3: Add the form**

Append to `pickem/pickem_superadmin/forms.py`:

```python
from pickem_api.models import Family


class FamilyRowForm(forms.ModelForm):
    class Meta:
        model = Family
        fields = ('name', 'slug', 'logo_url', 'status')
        widgets = {
            'name': forms.TextInput(attrs={'class': CELL}),
            'slug': forms.TextInput(attrs={'class': CELL + ' font-mono'}),
            'logo_url': forms.TextInput(attrs={'class': CELL}),
            'status': forms.Select(attrs={'class': CELL}),
        }
```

- [ ] **Step 4: Write the view**

`pickem/pickem_superadmin/views/families.py`:

```python
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from pickem_api.models import Family, FamilyMembership
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.forms import FamilyRowForm
from pickem_superadmin.models import SuperAdminAuditLog

TRACKED_FIELDS = ('name', 'slug', 'logo_url', 'status')


@superadmin_required
def families(request):
    family_qs = Family.objects.annotate(
        member_count=Count(
            'memberships',
            filter=Q(memberships__status=FamilyMembership.Status.ACTIVE),
            distinct=True,
        ),
        pool_count=Count('pools', distinct=True),
    ).order_by('name')

    rows = [
        {'family': family, 'form': FamilyRowForm(instance=family, prefix=str(family.id))}
        for family in family_qs
    ]
    return render(request, 'superadmin/families.html', {'rows': rows})


@superadmin_required
@require_POST
def families_save(request):
    saved, failed, stale = 0, [], []

    for family in Family.objects.all():
        prefix = str(family.id)
        if f'{prefix}-slug' not in request.POST:
            continue

        if request.POST.get(f'{prefix}-updated_at', '') != family.updated_at.isoformat():
            stale.append(family.slug)
            continue

        before = {f: getattr(family, f) for f in TRACKED_FIELDS}
        form = FamilyRowForm(request.POST, instance=family, prefix=prefix)
        if not form.is_valid():
            failed.append(family.slug)
            continue

        after = {f: form.cleaned_data[f] for f in TRACKED_FIELDS}
        changes = diff_fields(before, after)
        if not changes:
            continue

        with transaction.atomic():
            form.save()
            log_action(
                request,
                action=SuperAdminAuditLog.Action.FAMILY_UPDATED,
                target=family,
                summary=f'Updated family {family.slug}',
                changes=changes,
            )
        saved += 1

    if saved:
        messages.success(request, f'Saved {saved} family(ies).')
    if stale:
        messages.error(
            request,
            f'Not saved — changed since you loaded it: {", ".join(stale)}. Reload and retry.',
        )
    if failed:
        messages.error(request, f'Invalid values could not be saved: {", ".join(failed)}.')
    if not saved and not stale and not failed:
        messages.success(request, 'No changes.')

    return redirect('superadmin:families')
```

- [ ] **Step 5: Write the template**

`pickem/pickem_superadmin/templates/superadmin/families.html`:

```html
{% extends 'superadmin/base.html' %}
{% block title %}families{% endblock %}
{% block heading %}Families <span class="font-normal text-gray-500">({{ rows|length }})</span>{% endblock %}
{% block content %}
  <form method="post" action="{% url 'superadmin:families_save' %}">
    {% csrf_token %}
    <div class="overflow-x-auto border border-gray-300 bg-white">
      <table class="w-full border-collapse">
        <thead class="bg-gray-200 text-left">
          <tr>
            <th class="px-2 py-1 font-semibold">name</th>
            <th class="px-2 py-1 font-semibold">slug</th>
            <th class="px-2 py-1 font-semibold">logo url</th>
            <th class="px-2 py-1 font-semibold">status</th>
            <th class="px-2 py-1 font-semibold">members</th>
            <th class="px-2 py-1 font-semibold">pools</th>
            <th class="px-2 py-1 font-semibold">created</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
            <tr class="border-t border-gray-200 {% if row.family.status == 'inactive' %}bg-gray-100 text-gray-500{% endif %}">
              <input type="hidden" name="{{ row.family.id }}-updated_at"
                     value="{{ row.family.updated_at.isoformat }}">
              <td class="px-2 py-1">{{ row.form.name }}</td>
              <td class="px-2 py-1">{{ row.form.slug }}</td>
              <td class="px-2 py-1">{{ row.form.logo_url }}</td>
              <td class="px-2 py-1">{{ row.form.status }}</td>
              <td class="px-2 py-1 font-mono">
                <a href="{% url 'superadmin:users' %}" class="underline">{{ row.family.member_count }}</a>
              </td>
              <td class="px-2 py-1 font-mono">
                <a href="{% url 'superadmin:pools' %}?family={{ row.family.slug }}" class="underline">{{ row.family.pool_count }}</a>
              </td>
              <td class="px-2 py-1 text-gray-600">{{ row.family.created_at|date:"Y-m-d" }}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    <button type="submit" class="mt-3 border border-gray-800 bg-gray-800 px-3 py-1 text-white hover:bg-gray-700">
      Save changes
    </button>
  </form>
{% endblock %}
```

- [ ] **Step 6: Wire URLs, views export, nav, auth test**

`views/__init__.py`: add `from pickem_superadmin.views.families import families, families_save`, extend `__all__`.

`urls.py`: add

```python
    path('families/', views.families, name='families'),
    path('families/save/', views.families_save, name='families_save'),
```

`base.html` nav: add the `families` link (same pattern as `pools`).

`tests/test_auth.py`: add `'superadmin:families'` to `SUPERADMIN_URLS` and `('superadmin:families_save', [])` to `SUPERADMIN_POST_URLS`.

- [ ] **Step 7: Run the tests to verify they pass**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: PASS, 42 tests.

- [ ] **Step 8: Rebuild Tailwind and commit**

```bash
npm run build:prod
git add pickem/pickem_superadmin pickem/pickem_homepage/static/css/tailwind.css
git commit -m "$(cat <<'EOF'
feat(superadmin): add families page

Cross-family table with inline name/slug/logo_url/status editing, member and
pool counts, and the same stale-row rejection and audit writes as the pool
matrix.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Teams page with live contrast preview

Closes the standing TODO item: "Add `Teams.logo_contrast_preset` editing to the future superadmin page so team-brand contrast fixes do not require Django admin access."

**Files:**
- Create: `pickem/pickem_superadmin/views/teams.py`, `templates/superadmin/teams.html`, `tests/test_teams.py`
- Modify: `pickem/pickem_superadmin/forms.py`, `views/__init__.py`, `urls.py`, `base.html`, `tests/test_auth.py`
- Modify: `TODO.md:10`

**Interfaces:**
- Consumes: `log_action`, `diff_fields`.
- Produces: URL names `superadmin:teams` (GET), `superadmin:teams_save` (POST). `forms.TeamRowForm`.

First, confirm the exact `Teams` field names (the model uses non-obvious ones — `color` plus an alternate):

- [ ] **Step 1: Read the Teams model to get exact field names**

```bash
cd pickem && sed -n 403,425p pickem_api/models.py
```

Use the exact field names you see for the alternate color and logo fields in the form below — the plan assumes `color`, `alt_color`, `logo`, `teamName`, `teamWins`, `teamLosses`, but **the model is the source of truth**. If a name differs, use the model's name everywhere in this task.

- [ ] **Step 2: Write the failing test**

`pickem/pickem_superadmin/tests/test_teams.py`:

```python
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import Teams
from pickem_superadmin.models import SuperAdminAuditLog


class TeamsPageTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        # Adjust kwargs to the real Teams field names confirmed in Step 1.
        self.team = Teams.objects.create(id=1, color='002244')
        self.client.force_login(self.root)

    def _row(self, **overrides):
        payload = {
            f'{self.team.id}-color': '002244',
            f'{self.team.id}-logo_contrast_preset': 'default',
        }
        payload.update({f'{self.team.id}-{k}': v for k, v in overrides.items()})
        return payload

    def test_page_lists_teams(self):
        response = self.client.get(reverse('superadmin:teams'))
        self.assertEqual(response.status_code, 200)

    def test_saving_a_contrast_preset_persists_and_audits(self):
        self.client.post(
            reverse('superadmin:teams_save'),
            self._row(logo_contrast_preset='white-burst'),
        )
        self.team.refresh_from_db()
        self.assertEqual(self.team.logo_contrast_preset, 'white-burst')

        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.TEAM_UPDATED)
        self.assertEqual(
            entry.changes['logo_contrast_preset'], ['default', 'white-burst'],
        )

    def test_unchanged_row_writes_no_audit_entry(self):
        self.client.post(reverse('superadmin:teams_save'), self._row())
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)
```

- [ ] **Step 3: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin.tests.test_teams --settings=pickem.test_settings
```

Expected: FAIL — `NoReverseMatch: 'superadmin:teams'`.

- [ ] **Step 4: Add the form**

Append to `pickem/pickem_superadmin/forms.py` (using the real field names from Step 1):

```python
from pickem_api.models import Teams


class TeamRowForm(forms.ModelForm):
    class Meta:
        model = Teams
        fields = ('color', 'logo_contrast_preset')
        widgets = {
            'color': forms.TextInput(attrs={'class': CELL + ' font-mono w-20'}),
            'logo_contrast_preset': forms.Select(attrs={'class': CELL}),
        }
```

If the model has an alternate-color field (confirmed in Step 1), add it to `fields` and `widgets` with the same `font-mono w-20` styling.

- [ ] **Step 5: Write the view**

`pickem/pickem_superadmin/views/teams.py`:

```python
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from pickem_api.models import Teams
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.forms import TeamRowForm
from pickem_superadmin.models import SuperAdminAuditLog

TRACKED_FIELDS = tuple(TeamRowForm.Meta.fields)


@superadmin_required
def teams(request):
    rows = [
        {'team': team, 'form': TeamRowForm(instance=team, prefix=str(team.id))}
        for team in Teams.objects.all().order_by('id')
    ]
    return render(request, 'superadmin/teams.html', {'rows': rows})


@superadmin_required
@require_POST
def teams_save(request):
    saved, failed = 0, []

    for team in Teams.objects.all():
        prefix = str(team.id)
        if f'{prefix}-logo_contrast_preset' not in request.POST:
            continue

        before = {f: getattr(team, f) for f in TRACKED_FIELDS}
        form = TeamRowForm(request.POST, instance=team, prefix=prefix)
        if not form.is_valid():
            failed.append(str(team.id))
            continue

        after = {f: form.cleaned_data[f] for f in TRACKED_FIELDS}
        changes = diff_fields(before, after)
        if not changes:
            continue

        with transaction.atomic():
            form.save()
            log_action(
                request,
                action=SuperAdminAuditLog.Action.TEAM_UPDATED,
                target=team,
                summary=f'Updated team {team.id}',
                changes=changes,
            )
        saved += 1

    if saved:
        messages.success(request, f'Saved {saved} team(s).')
    if failed:
        messages.error(request, f'Invalid values could not be saved: {", ".join(failed)}.')
    if not saved and not failed:
        messages.success(request, 'No changes.')

    return redirect('superadmin:teams')
```

- [ ] **Step 6: Write the template with the live preview swatch**

`pickem/pickem_superadmin/templates/superadmin/teams.html`. The preview is the point: you see the contrast fix instead of guessing from hex.

```html
{% extends 'superadmin/base.html' %}
{% block title %}teams{% endblock %}
{% block heading %}Teams <span class="font-normal text-gray-500">({{ rows|length }})</span>{% endblock %}
{% block content %}
  <p class="mb-3 text-gray-600">
    The preview shows the logo on its brand-color background — the exact case the
    contrast preset exists to fix. Change the preset, save, and look.
  </p>

  <form method="post" action="{% url 'superadmin:teams_save' %}">
    {% csrf_token %}
    <div class="overflow-x-auto border border-gray-300 bg-white">
      <table class="w-full border-collapse">
        <thead class="bg-gray-200 text-left">
          <tr>
            <th class="px-2 py-1 font-semibold">id</th>
            <th class="px-2 py-1 font-semibold">team</th>
            <th class="px-2 py-1 font-semibold">color</th>
            <th class="px-2 py-1 font-semibold">contrast preset</th>
            <th class="px-2 py-1 font-semibold">preview</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
            <tr class="border-t border-gray-200">
              <td class="px-2 py-1 font-mono">{{ row.team.id }}</td>
              <td class="px-2 py-1">{{ row.team }}</td>
              <td class="px-2 py-1">{{ row.form.color }}</td>
              <td class="px-2 py-1">{{ row.form.logo_contrast_preset }}</td>
              <td class="px-2 py-1">
                <div class="flex h-12 w-24 items-center justify-center border border-gray-300"
                     style="background: linear-gradient(135deg, #{{ row.team.color|default:'333333' }}, #{{ row.team.color|default:'333333' }}cc);">
                  {% if row.team.logo_contrast_preset == 'white-burst' %}
                    <div class="flex h-10 w-10 items-center justify-center rounded-full bg-white/60">
                      <span class="font-mono text-gray-800">{{ row.team.id }}</span>
                    </div>
                  {% else %}
                    <span class="font-mono text-white">{{ row.team.id }}</span>
                  {% endif %}
                </div>
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    <button type="submit" class="mt-3 border border-gray-800 bg-gray-800 px-3 py-1 text-white hover:bg-gray-700">
      Save changes
    </button>
  </form>
{% endblock %}
```

If the `Teams` model has a logo URL field (confirmed in Step 1), replace the `<span>` placeholder inside the swatch with `<img src="{{ row.team.logo }}" class="h-10 w-10 object-contain">` so the preview shows the real logo.

- [ ] **Step 7: Wire URLs, views export, nav, auth test**

`views/__init__.py`: add `from pickem_superadmin.views.teams import teams, teams_save`, extend `__all__`.

`urls.py`: add

```python
    path('teams/', views.teams, name='teams'),
    path('teams/save/', views.teams_save, name='teams_save'),
```

`base.html` nav: add the `teams` link.

`tests/test_auth.py`: add `'superadmin:teams'` to `SUPERADMIN_URLS` and `('superadmin:teams_save', [])` to `SUPERADMIN_POST_URLS`.

- [ ] **Step 8: Tick the TODO item**

In `TODO.md`, line 10, change:

```markdown
- [ ] Add `Teams.logo_contrast_preset` editing to the future superadmin page so team-brand contrast fixes do not require Django admin access.
```

to:

```markdown
- [x] Add `Teams.logo_contrast_preset` editing to the future superadmin page so team-brand contrast fixes do not require Django admin access. Done 2026-07-13: the `/superadmin/teams/` page edits `logo_contrast_preset` and team colors inline, with a live preview swatch rendering the logo on its brand background.
```

- [ ] **Step 9: Run the tests to verify they pass**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: PASS, 47 tests.

- [ ] **Step 10: Rebuild Tailwind and commit**

```bash
npm run build:prod
git add pickem/pickem_superadmin pickem/pickem_homepage/static/css/tailwind.css TODO.md
git commit -m "$(cat <<'EOF'
feat(superadmin): add teams page with live contrast preview

Edit logo_contrast_preset and team colors without Django admin, with a preview
swatch rendering the logo on its brand-color background so contrast fixes are
seen rather than guessed. Closes the standing TODO item.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Jobs page — queue runs and scheduler health

**Files:**
- Create: `pickem/pickem_superadmin/jobs.py`, `views/jobs.py`, `templates/superadmin/jobs.html`, `tests/test_jobs.py`
- Modify: `pickem/pickem_superadmin/views/__init__.py`, `urls.py`, `base.html`, `tests/test_auth.py`
- Modify: `pickem/pickem_homepage/views.py:1078-1110` (delete `family_pool_admin_job_runs`)
- Modify: `pickem/pickem_homepage/urls.py:76-79` (delete its route)
- Delete: `pickem/pickem_homepage/templates/pickem/family_admin_job_runs.html`
- Modify: `pickem/pickem_homepage/templates/pickem/family_admin.html` (remove the Job Runs card, link to `/superadmin/jobs/` instead)

**Interfaces:**
- Consumes: `log_action`.
- Produces:
  - `jobs.QUEUEABLE_COMMANDS` — tuple of command names.
  - `jobs.run_command(command_name)` — module-level function APScheduler can import and call.
  - `jobs.queue_command(command_name) -> str` (the job id). Raises `ValueError` for an unknown command.
  - `jobs.scheduler_health() -> dict` with keys `alive` (bool), `last_run` (datetime|None), `last_status` (str|None), `stale` (bool).
  - URL names `superadmin:jobs` (GET), `superadmin:jobs_queue` (POST).

- [ ] **Step 1: Write the failing test**

`pickem/pickem_superadmin/tests/test_jobs.py`:

```python
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_superadmin import jobs
from pickem_superadmin.models import SuperAdminAuditLog


class QueueCommandTests(TestCase):
    def test_rejects_a_command_that_is_not_allowlisted(self):
        """Never let a POST body name an arbitrary management command."""
        with self.assertRaises(ValueError):
            jobs.queue_command('flush')

    @patch('pickem_superadmin.jobs.get_scheduler')
    def test_queues_an_allowlisted_command_as_a_one_off_job(self, get_scheduler):
        job_id = jobs.queue_command('update_standings')

        scheduler = get_scheduler.return_value
        scheduler.add_job.assert_called_once()
        kwargs = scheduler.add_job.call_args.kwargs
        self.assertEqual(kwargs['args'], ['update_standings'])
        self.assertEqual(kwargs['trigger'], 'date')
        self.assertTrue(job_id.startswith('manual:update_standings:'))


class JobsPageTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.client.force_login(self.root)

    def test_page_renders(self):
        self.assertEqual(self.client.get(reverse('superadmin:jobs')).status_code, 200)

    @patch('pickem_superadmin.views.jobs.jobs.queue_command')
    @patch('pickem_superadmin.views.jobs.jobs.scheduler_health')
    def test_queueing_a_job_audits_it(self, health, queue_command):
        health.return_value = {'alive': True, 'last_run': None, 'last_status': None, 'stale': False}
        queue_command.return_value = 'manual:update_standings:123'

        self.client.post(
            reverse('superadmin:jobs_queue'), {'command': 'update_standings'},
        )

        queue_command.assert_called_once_with('update_standings')
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.JOB_QUEUED)
        self.assertIn('update_standings', entry.summary)

    @patch('pickem_superadmin.views.jobs.jobs.queue_command')
    @patch('pickem_superadmin.views.jobs.jobs.scheduler_health')
    def test_refuses_to_queue_when_no_scheduler_is_alive(self, health, queue_command):
        """Otherwise the job sits in the jobstore forever and the operator never
        learns why nothing happened."""
        health.return_value = {'alive': False, 'last_run': None, 'last_status': None, 'stale': True}

        response = self.client.post(
            reverse('superadmin:jobs_queue'), {'command': 'update_standings'}, follow=True,
        )

        queue_command.assert_not_called()
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)
        self.assertContains(response, 'no live scheduler')

    @patch('pickem_superadmin.views.jobs.jobs.scheduler_health')
    def test_rejects_a_command_outside_the_allowlist(self, health):
        health.return_value = {'alive': True, 'last_run': None, 'last_status': None, 'stale': False}
        self.client.post(reverse('superadmin:jobs_queue'), {'command': 'flush'})
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin.tests.test_jobs --settings=pickem.test_settings
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pickem_superadmin.jobs'`.

- [ ] **Step 3: Write the jobs module**

`pickem/pickem_superadmin/jobs.py`:

```python
"""Queueing pipeline runs.

We do NOT run commands in the web request: update_games makes ESPN calls and
update_all chains the whole pipeline, so either could outlive a gunicorn worker
timeout, and a browser refresh would fire it twice.

Instead we write a one-off job into the APScheduler DjangoJobStore, which is the
database. The scheduler process (the one with RUN_SCHEDULER=true) picks it up on
its next wakeup — at most ~60s away, since update_all already runs every minute —
and django-apscheduler records the execution, so run history needs no new code.

The tradeoff is real: the job is enqueued, not instant. The UI says so.
"""
import time
from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone

# Allowlist. A POST body must never be able to name an arbitrary management
# command — that would be remote command execution with a superuser session.
QUEUEABLE_COMMANDS = (
    'update_all',
    'update_games',
    'update_picks',
    'update_standings',
    'update_stats',
    'update_records',
    'update_weekly_winners',
    'update_season_winners',
    'update_missed_picks',
    'update_rankings',
)

# If the scheduler has not executed anything in this long, treat it as dead.
# update_all runs every minute, so 5 minutes of silence is unambiguous.
STALE_AFTER = timedelta(minutes=5)


def run_command(command_name):
    """APScheduler job target. Must be importable at module level."""
    if command_name not in QUEUEABLE_COMMANDS:
        raise ValueError(f'Command not allowed: {command_name}')
    call_command(command_name)


def get_scheduler():
    """The live scheduler in this process, or a jobstore-only scheduler that can
    still write to the shared DjangoJobStore from a web worker."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from django.conf import settings
    from django_apscheduler.jobstores import DjangoJobStore

    from pickem_api import scheduler as scheduler_module

    if scheduler_module._scheduler is not None:
        return scheduler_module._scheduler

    # This process has no running scheduler (a plain web worker). Build one just
    # to reach the jobstore; we never .start() it, so it only writes the row.
    writer = BackgroundScheduler(timezone=settings.TIME_ZONE)
    writer.add_jobstore(DjangoJobStore(), 'default')
    return writer


def queue_command(command_name):
    """Enqueue a one-off run. Returns the job id."""
    if command_name not in QUEUEABLE_COMMANDS:
        raise ValueError(f'Command not allowed: {command_name}')

    job_id = f'manual:{command_name}:{int(time.time())}'
    get_scheduler().add_job(
        run_command,
        trigger='date',
        run_date=timezone.now(),
        id=job_id,
        name=f'Manual run: {command_name}',
        args=[command_name],
        max_instances=1,
        replace_existing=True,
    )
    return job_id


def scheduler_health():
    """Is anything actually executing jobs? A queued job on a dead scheduler sits
    in the jobstore forever, so the console must be able to tell."""
    from django_apscheduler.models import DjangoJobExecution

    last = DjangoJobExecution.objects.order_by('-run_time').first()
    if last is None:
        return {'alive': False, 'last_run': None, 'last_status': None, 'stale': True}

    stale = (timezone.now() - last.run_time) > STALE_AFTER
    return {
        'alive': not stale,
        'last_run': last.run_time,
        'last_status': last.status,
        'stale': stale,
    }
```

- [ ] **Step 4: Write the view**

`pickem/pickem_superadmin/views/jobs.py`:

```python
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from pickem_superadmin import jobs
from pickem_superadmin.audit import log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.models import SuperAdminAuditLog


@superadmin_required
def jobs_page(request):
    from django_apscheduler.models import DjangoJob, DjangoJobExecution

    executions = Paginator(
        DjangoJobExecution.objects.select_related('job').order_by('-run_time'), 25,
    ).get_page(request.GET.get('page'))

    return render(request, 'superadmin/jobs.html', {
        'registered_jobs': DjangoJob.objects.all().order_by('id'),
        'executions': executions,
        'queueable': jobs.QUEUEABLE_COMMANDS,
        'health': jobs.scheduler_health(),
    })


@superadmin_required
@require_POST
def jobs_queue(request):
    command = request.POST.get('command', '')

    if not jobs.scheduler_health()['alive']:
        messages.error(
            request,
            'Not queued: no live scheduler. A queued job would sit in the jobstore '
            'and never run. Check that a process has RUN_SCHEDULER=true.',
        )
        return redirect('superadmin:jobs')

    try:
        job_id = jobs.queue_command(command)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('superadmin:jobs')

    log_action(
        request,
        action=SuperAdminAuditLog.Action.JOB_QUEUED,
        target=None,
        summary=f'Queued pipeline run: {command}',
        changes={'job_id': [None, job_id]},
    )
    messages.success(
        request,
        f'Queued {command}. It runs on the scheduler within ~60s — watch the history below.',
    )
    return redirect('superadmin:jobs')
```

- [ ] **Step 5: Write the template**

`pickem/pickem_superadmin/templates/superadmin/jobs.html`:

```html
{% extends 'superadmin/base.html' %}
{% block title %}jobs{% endblock %}
{% block heading %}Jobs{% endblock %}
{% block content %}
  {% if health.alive %}
    <div class="mb-3 border-l-4 border-green-600 bg-green-50 px-3 py-2 text-green-900">
      Scheduler alive — last run {{ health.last_run|date:"Y-m-d H:i:s" }} ({{ health.last_status }}).
    </div>
  {% else %}
    <div class="mb-3 border-l-4 border-red-600 bg-red-50 px-3 py-2 text-red-900">
      <strong>No live scheduler.</strong>
      {% if health.last_run %}
        Nothing has executed since {{ health.last_run|date:"Y-m-d H:i:s" }}.
      {% else %}
        Nothing has ever executed.
      {% endif %}
      Queueing is disabled — a queued job would sit in the jobstore and never run.
      Check that a process has <span class="font-mono">RUN_SCHEDULER=true</span>.
    </div>
  {% endif %}

  <h2 class="mb-1 font-semibold">Queue a run</h2>
  <p class="mb-2 text-gray-600">
    Jobs are <em>enqueued</em>, not run immediately. The scheduler picks them up on its
    next wakeup (~60s) and the run appears in the history below.
  </p>
  <form method="post" action="{% url 'superadmin:jobs_queue' %}" class="mb-5 flex gap-2">
    {% csrf_token %}
    <select name="command" class="border border-gray-300 px-2 py-1 font-mono">
      {% for command in queueable %}<option value="{{ command }}">{{ command }}</option>{% endfor %}
    </select>
    <button type="submit" {% if not health.alive %}disabled{% endif %}
            class="border border-gray-800 bg-gray-800 px-3 py-1 text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:border-gray-400 disabled:bg-gray-400">
      Queue run
    </button>
  </form>

  <h2 class="mb-1 font-semibold">Registered jobs</h2>
  <div class="mb-5 overflow-x-auto border border-gray-300 bg-white">
    <table class="w-full border-collapse">
      <thead class="bg-gray-200 text-left">
        <tr>
          <th class="px-2 py-1 font-semibold">id</th>
          <th class="px-2 py-1 font-semibold">next run</th>
        </tr>
      </thead>
      <tbody>
        {% for job in registered_jobs %}
          <tr class="border-t border-gray-200">
            <td class="px-2 py-1 font-mono">{{ job.id }}</td>
            <td class="px-2 py-1 font-mono">{{ job.next_run_time|date:"Y-m-d H:i:s"|default:"—" }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <h2 class="mb-1 font-semibold">Run history</h2>
  <div class="overflow-x-auto border border-gray-300 bg-white">
    <table class="w-full border-collapse">
      <thead class="bg-gray-200 text-left">
        <tr>
          <th class="px-2 py-1 font-semibold">job</th>
          <th class="px-2 py-1 font-semibold">run time</th>
          <th class="px-2 py-1 font-semibold">status</th>
          <th class="px-2 py-1 font-semibold">duration</th>
          <th class="px-2 py-1 font-semibold">exception</th>
        </tr>
      </thead>
      <tbody>
        {% for execution in executions %}
          <tr class="border-t border-gray-200 {% if execution.exception %}bg-red-50{% endif %}">
            <td class="px-2 py-1 font-mono">{{ execution.job_id }}</td>
            <td class="px-2 py-1 font-mono">{{ execution.run_time|date:"Y-m-d H:i:s" }}</td>
            <td class="px-2 py-1">{{ execution.status }}</td>
            <td class="px-2 py-1 font-mono">{{ execution.duration|default:"—" }}</td>
            <td class="px-2 py-1 font-mono text-red-800">{{ execution.exception|default:"" }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  {% if executions.has_other_pages %}
    <div class="mt-2 flex gap-2">
      {% if executions.has_previous %}
        <a href="?page={{ executions.previous_page_number }}" class="underline">&larr; prev</a>
      {% endif %}
      <span class="text-gray-600">page {{ executions.number }} of {{ executions.paginator.num_pages }}</span>
      {% if executions.has_next %}
        <a href="?page={{ executions.next_page_number }}" class="underline">next &rarr;</a>
      {% endif %}
    </div>
  {% endif %}
{% endblock %}
```

- [ ] **Step 6: Wire URLs, views export, nav, auth test**

`views/__init__.py`: add `from pickem_superadmin.views.jobs import jobs_page, jobs_queue`, extend `__all__`.

`urls.py`: add

```python
    path('jobs/', views.jobs_page, name='jobs'),
    path('jobs/queue/', views.jobs_queue, name='jobs_queue'),
```

`base.html` nav: add the `jobs` link.

`tests/test_auth.py`: add `'superadmin:jobs'` to `SUPERADMIN_URLS` and `('superadmin:jobs_queue', [])` to `SUPERADMIN_POST_URLS`.

- [ ] **Step 7: Remove the old family-scoped job runs page**

The scheduler is system-wide, yet that page was reachable only by first picking an arbitrary family. It moves here.

- Delete `family_pool_admin_job_runs` from `pickem/pickem_homepage/views.py` (lines ~1078-1110).
- Delete its route from `pickem/pickem_homepage/urls.py` (lines ~76-79).
- Delete `pickem/pickem_homepage/templates/pickem/family_admin_job_runs.html`.
- In `pickem/pickem_homepage/templates/pickem/family_admin.html`, remove the "Job Runs" card. If you want superusers to still find it, replace the card's `href` with `/superadmin/jobs/` and wrap the card in `{% if request.user.is_superuser %}`.
- Delete any test in `pickem/pickem_homepage/tests.py` that references `family_pool_admin_job_runs`. Find them first:

```bash
cd pickem && grep -rn "job_runs" pickem_homepage/
```

- [ ] **Step 8: Run the full suite**

```bash
cd pickem && python manage.py test --settings=pickem.test_settings
```

Expected: PASS. The superadmin app contributes 55 tests; the homepage suite loses whatever `job_runs` tests existed. If anything else fails, it is a real regression from the removal — fix it before committing.

- [ ] **Step 9: Rebuild Tailwind and commit**

```bash
npm run build:prod
git add -A
git commit -m "$(cat <<'EOF'
feat(superadmin): add jobs page and retire the family-scoped job runs page

Queue pipeline runs by writing a one-off job into the APScheduler DjangoJobStore
rather than running them in the web request. Commands are allowlisted so a POST
body cannot name an arbitrary management command. Queueing is refused when no
scheduler is alive, since the job would otherwise sit in the jobstore forever.

The system-wide job runs page moves out of the family admin hub, where it was
reachable only by first picking an arbitrary family.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Repair services + `--pool` support on the update commands

**Files:**
- Modify: `pickem/pickem_api/management/commands/update_standings.py:49-56` (add `--pool`)
- Modify: `pickem/pickem_api/management/commands/update_stats.py:55-62` (add `--pool`)
- Modify: `pickem/pickem_superadmin/services.py` (add repair functions)
- Modify: `pickem/pickem_superadmin/tests/test_services.py` (add repair tests)

**Interfaces:**
- Consumes: `log_action`.
- Produces:
  - `update_standings --pool <id>` and `update_stats --pool <id>` (both optional; absent = all pools, unchanged behavior).
  - `services.recompute_pool(request, pool) -> dict` — re-runs standings + stats scoped to one pool. Idempotent.
  - `services.backfill_pool_settings(request, pool) -> PoolSettings` — creates the default row. Idempotent.
  - `services.delete_pick(request, pick) -> dict` — destructive.
  - `services.reset_season_row(request, season_points) -> dict` — destructive.

Note: neither `update_standings` nor `update_stats` currently accepts a pool argument — they are season-scoped only. Pool-scoped recompute is impossible without adding it, which is why this task touches them.

- [ ] **Step 1: Write the failing test**

Append to `pickem/pickem_superadmin/tests/test_services.py`:

```python
from io import StringIO

from django.core.management import call_command

from pickem_api.models import (
    Family, FamilyAuditLog, GamePicks, GamesAndScores, Pool, PoolSettings,
    userSeasonPoints, userStats,
)


class PoolScopedCommandTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool_a = Pool.objects.create(
            family=self.family, name='A', slug='a', season=2627,
        )
        self.pool_b = Pool.objects.create(
            family=self.family, name='B', slug='b', season=2627,
        )
        # A scored pick in each pool, so a season-wide run would touch both.
        for pool, user_id in ((self.pool_a, 'alice'), (self.pool_b, 'bob')):
            GamePicks.objects.create(
                id=f'{pool.slug}-{user_id}-1', pool=pool, userID=user_id,
                pick='ne', gameseason=2627, pick_correct=True,
            )

    def test_update_standings_with_pool_touches_only_that_pool(self):
        """Without --pool there is no way to recompute one pool, which is what the
        repair action needs. The point is the *scoping*, so assert pool B is
        untouched — a test that only asserts pool A got a row would pass even if
        the filter were ignored entirely."""
        call_command(
            'update_standings', season=2627, pool=self.pool_a.id, stdout=StringIO(),
        )

        self.assertTrue(userSeasonPoints.objects.filter(pool=self.pool_a).exists())
        self.assertFalse(userSeasonPoints.objects.filter(pool=self.pool_b).exists())

    def test_update_standings_without_pool_still_touches_every_pool(self):
        """The existing season-wide behavior must not regress."""
        call_command('update_standings', season=2627, stdout=StringIO())

        self.assertTrue(userSeasonPoints.objects.filter(pool=self.pool_a).exists())
        self.assertTrue(userSeasonPoints.objects.filter(pool=self.pool_b).exists())

    def test_update_stats_with_pool_touches_only_that_pool(self):
        call_command('update_stats', season=2627, pool=self.pool_a.id, stdout=StringIO())

        self.assertTrue(userStats.objects.filter(pool=self.pool_a).exists())
        self.assertFalse(userStats.objects.filter(pool=self.pool_b).exists())


class RepairServiceTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )

    def _request(self):
        request = RequestFactory().post('/superadmin/')
        request.user = self.root
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        return request

    def test_backfill_creates_the_missing_settings_row(self):
        self.assertFalse(PoolSettings.objects.filter(pool=self.pool).exists())
        services.backfill_pool_settings(self._request(), self.pool)
        self.assertTrue(PoolSettings.objects.filter(pool=self.pool).exists())

    def test_backfill_is_idempotent(self):
        services.backfill_pool_settings(self._request(), self.pool)
        services.backfill_pool_settings(self._request(), self.pool)
        self.assertEqual(PoolSettings.objects.filter(pool=self.pool).count(), 1)

    def test_backfill_audits_and_dual_writes(self):
        services.backfill_pool_settings(self._request(), self.pool)
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.DATA_REPAIR)
        self.assertEqual(FamilyAuditLog.objects.count(), 1)

    def test_recompute_pool_is_idempotent(self):
        """Running it twice must not double points — this is the workhorse action
        and it has to be safe to spam."""
        services.recompute_pool(self._request(), self.pool)
        first = list(
            userSeasonPoints.objects.filter(pool=self.pool)
            .order_by('id').values_list('total_points', flat=True)
        )
        services.recompute_pool(self._request(), self.pool)
        second = list(
            userSeasonPoints.objects.filter(pool=self.pool)
            .order_by('id').values_list('total_points', flat=True)
        )
        self.assertEqual(first, second)

    def test_recompute_pool_audits(self):
        services.recompute_pool(self._request(), self.pool)
        self.assertTrue(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.DATA_REPAIR,
            ).exists()
        )

    def test_delete_pick_records_the_row_before_deleting_it(self):
        """This one is not reversible, so the audit row is the only record of what
        was there."""
        pick = GamePicks.objects.create(
            id='dagostino-pickem-pool-root-1', pool=self.pool, userID='root',
            pick='ne', gameseason=2627,
        )
        services.delete_pick(self._request(), pick)

        self.assertFalse(GamePicks.objects.filter(pk='dagostino-pickem-pool-root-1').exists())
        entry = SuperAdminAuditLog.objects.filter(
            action=SuperAdminAuditLog.Action.DATA_REPAIR,
        ).latest('created_at')
        self.assertEqual(entry.changes['pick'][0], 'ne')
        self.assertIsNone(entry.changes['pick'][1])

    def test_rescore_week_clears_scoring_then_recomputes(self):
        """A corrected game result must actually flip a wrong pick. If rescore only
        recomputed without clearing, an already-scored pick would stay wrong."""
        pick = GamePicks.objects.create(
            id='dagostino-pickem-pool-root-1', pool=self.pool, userID='root',
            pick='ne', gameseason=2627, gameWeek=1, pick_correct=True,
        )

        services.rescore_week(self._request(), self.pool, week=1)

        pick.refresh_from_db()
        # No finished game backs this pick, so rescoring must not leave it credited.
        self.assertFalse(pick.pick_correct)
        self.assertTrue(
            SuperAdminAuditLog.objects.filter(
                action=SuperAdminAuditLog.Action.DATA_REPAIR,
                summary__contains='Re-scored week 1',
            ).exists()
        )

    def test_fix_stuck_game_records_before_and_after(self):
        game = GamesAndScores.objects.create(
            id=401, slug='ne-at-nyj', gameyear='2026', gameseason=2627,
        )
        before_status = game.gameStatus

        services.fix_stuck_game(
            self._request(), game, status='STATUS_FINAL', home_score=21, away_score=17,
        )

        game.refresh_from_db()
        self.assertEqual(game.gameStatus, 'STATUS_FINAL')
        entry = SuperAdminAuditLog.objects.filter(
            action=SuperAdminAuditLog.Action.DATA_REPAIR,
        ).latest('created_at')
        self.assertEqual(entry.changes['gameStatus'], [before_status, 'STATUS_FINAL'])
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin.tests.test_services --settings=pickem.test_settings
```

Expected: FAIL — `CommandError: unrecognized arguments: --pool`.

- [ ] **Step 3: Add `--pool` to update_standings**

In `pickem/pickem_api/management/commands/update_standings.py`, add to `add_arguments`:

```python
        parser.add_argument(
            "--pool",
            type=int,
            default=None,
            help="Limit the recompute to a single pool id (defaults to every pool).",
        )
```

And in `handle`, after `season = options["season"] or get_season()`:

```python
        pool_id = options.get("pool")
```

Then filter the pick query — change:

```python
        pick_combos = (
            GamePicks.objects.filter(gameseason=season)
```

to:

```python
        pick_filter = {"gameseason": season}
        if pool_id:
            pick_filter["pool_id"] = pool_id

        pick_combos = (
            GamePicks.objects.filter(**pick_filter)
```

Read the rest of `handle` and apply the same `pool_id` filter to **every** queryset that enumerates pools or standings rows — including the block that gives "every active member of this season's pools a standings row". If you leave one unfiltered, a pool-scoped recompute will still touch other pools, which defeats the point. Verify by reading the whole `handle` before moving on.

- [ ] **Step 4: Add `--pool` to update_stats**

Same shape in `pickem/pickem_api/management/commands/update_stats.py`: add the `--pool` argument, read `pool_id = options.get("pool")` in `handle`, and filter every pool-enumerating queryset by it.

Note `update_stats` writes one global pool-null row per user (per the TODO history). When `--pool` is given, scope to that pool's rows and leave the global row alone unless the command already recomputes it from all pools — read the code and preserve its existing semantics.

- [ ] **Step 5: Add the repair services**

Append to `pickem/pickem_superadmin/services.py`:

```python
from django.core.management import call_command

from pickem_api.models import FamilyAuditLog, GamePicks, PoolSettings, userSeasonPoints


@transaction.atomic
def backfill_pool_settings(request, pool):
    """Create the default PoolSettings row for a pool that has none. Idempotent."""
    settings_obj, created = PoolSettings.objects.get_or_create(pool=pool)
    if created:
        log_action(
            request,
            action=SuperAdminAuditLog.Action.DATA_REPAIR,
            target=pool,
            summary=f'Backfilled PoolSettings for {pool.family.slug}/{pool.slug}',
            changes={'pool_settings': [None, 'created with defaults']},
            family=pool.family,
            pool=pool,
            family_action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
        )
    return settings_obj


def recompute_pool(request, pool):
    """Re-run standings + stats scoped to one pool. Idempotent — safe to spam.

    Not wrapped in transaction.atomic: the commands manage their own writes and
    can be long-running, so holding one transaction open across both would pin a
    connection for no benefit. Re-running on failure is safe precisely because
    this is idempotent.
    """
    call_command('update_standings', season=pool.season, pool=pool.id)
    call_command('update_stats', season=pool.season, pool=pool.id)

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=pool,
        summary=f'Recomputed standings + stats for {pool.family.slug}/{pool.slug}',
        changes={'recompute': [None, f'season {pool.season}']},
        family=pool.family,
        pool=pool,
        family_action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED,
    )
    return {'pool': pool.id, 'season': pool.season}


@transaction.atomic
def delete_pick(request, pick):
    """Destructive and NOT reversible. The audit row is the only record of what the
    pick was, so capture it before deleting."""
    before = {
        'pick': [pick.pick, None],
        'pick_game_id': [pick.pick_game_id, None],
        'userID': [pick.userID, None],
        'id': [pick.id, None],
    }
    pool = pick.pool
    pick.delete()

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=pool,
        summary=f'Deleted pick {before["id"][0]}',
        changes=before,
        family=pool.family if pool else None,
        pool=pool,
        family_action=FamilyAuditLog.Action.MANUAL_PICK_UPDATED if pool else None,
    )
    return before


@transaction.atomic
def reset_season_row(request, season_points):
    """Destructive: delete a drifted userSeasonPoints row so a recompute rebuilds it
    from scratch. Capture the totals first — this is not reversible."""
    pool = season_points.pool
    before = {
        'userID': [season_points.userID, None],
        'total_points': [season_points.total_points, None],
    }
    season_points.delete()

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=pool,
        summary=f'Reset season row for {before["userID"][0]}',
        changes=before,
        family=pool.family if pool else None,
        pool=pool,
        family_action=FamilyAuditLog.Action.POOL_SETTINGS_UPDATED if pool else None,
    )
    return before


def rescore_week(request, pool, week):
    """Re-score one week after a game result is corrected.

    Clearing first is the whole point: update_picks only scores *unscored* picks,
    so recomputing without clearing would leave an already-scored (and now wrong)
    pick exactly as wrong as it was. Idempotent.
    """
    GamePicks.objects.filter(pool=pool, gameseason=pool.season, gameWeek=week).update(
        pick_correct=False,
    )
    call_command('update_picks', season=pool.season)
    call_command('update_standings', season=pool.season, pool=pool.id)

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=pool,
        summary=f'Re-scored week {week} for {pool.family.slug}/{pool.slug}',
        changes={'rescore_week': [None, week]},
        family=pool.family,
        pool=pool,
        family_action=FamilyAuditLog.Action.MANUAL_PICK_UPDATED,
    )
    return {'pool': pool.id, 'week': week}


@transaction.atomic
def fix_stuck_game(request, game, status, home_score, away_score):
    """Unwedge a game ESPN left in progress forever. Destructive: it overwrites
    what the feed reported, so record both sides."""
    before = {
        'gameStatus': game.gameStatus,
        HOME_SCORE_FIELD: getattr(game, HOME_SCORE_FIELD),
        AWAY_SCORE_FIELD: getattr(game, AWAY_SCORE_FIELD),
    }

    game.gameStatus = status
    setattr(game, HOME_SCORE_FIELD, home_score)
    setattr(game, AWAY_SCORE_FIELD, away_score)
    game.save(update_fields=['gameStatus', HOME_SCORE_FIELD, AWAY_SCORE_FIELD])

    after = {
        'gameStatus': game.gameStatus,
        HOME_SCORE_FIELD: getattr(game, HOME_SCORE_FIELD),
        AWAY_SCORE_FIELD: getattr(game, AWAY_SCORE_FIELD),
    }
    changes = diff_fields(before, after)

    log_action(
        request,
        action=SuperAdminAuditLog.Action.DATA_REPAIR,
        target=game,
        summary=f'Fixed stuck game {game.slug} -> {status}',
        changes=changes,
    )
    return changes
```

`fix_stuck_game` uses `HOME_SCORE_FIELD` / `AWAY_SCORE_FIELD` constants because the real field names on `GamesAndScores` must be read from the model, not guessed. Confirm them and define the constants at the top of `services.py`:

```bash
cd pickem && sed -n 426,478p pickem_api/models.py
```

Then add near the imports in `services.py`, replacing the right-hand strings with the model's actual names, and import `diff_fields` alongside `log_action`:

```python
from pickem_superadmin.audit import diff_fields, log_action

# Confirmed against pickem_api.models.GamesAndScores.
HOME_SCORE_FIELD = 'homeScore'
AWAY_SCORE_FIELD = 'awayScore'
```

Update the test in Step 1 to use the same real names if they differ from `home_score`/`away_score`.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: PASS, zero failures (this task adds the pool-scoped-command and repair-service tests).

- [ ] **Step 7: Run the full suite — the command changes touch the pipeline**

```bash
cd pickem && python manage.py test --settings=pickem.test_settings
```

Expected: PASS. `--pool` defaults to `None`, so existing season-wide behavior is unchanged. If a pipeline test fails, you filtered a queryset you should not have — reread Step 3.

- [ ] **Step 8: Commit**

```bash
git add pickem/pickem_superadmin pickem/pickem_api/management/commands
git commit -m "$(cat <<'EOF'
feat(superadmin): add repair services and pool-scoped recompute

update_standings and update_stats gain an optional --pool filter (absent = every
pool, unchanged), which is what makes a pool-scoped recompute possible at all.
Repair services capture before/after into the audit log — the delete/reset ones
are not reversible, so that row is the only record of what was there.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Overview — health, anomalies, and site settings

The landing page, built last because it links to everything else.

**Files:**
- Modify: `pickem/pickem_superadmin/views/overview.py`, `templates/superadmin/overview.html`
- Create: `pickem/pickem_superadmin/tests/test_overview.py`
- Modify: `pickem/pickem_superadmin/urls.py`, `views/__init__.py`, `tests/test_auth.py`

**Interfaces:**
- Consumes: `jobs.scheduler_health`, `services.backfill_pool_settings`, `log_action`, `diff_fields`.
- Produces: URL names `superadmin:overview` (already exists), `superadmin:season_update` (POST), `superadmin:pool_settings_backfill` (POST, `<int:pool_id>`), `superadmin:banner_publish` (POST), `superadmin:banner_deactivate` (POST, `<int:banner_id>`).

- [ ] **Step 1: Write the failing test**

`pickem/pickem_superadmin/tests/test_overview.py`:

```python
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_api.models import Family, Pool, PoolSettings, currentSeason
from pickem_homepage.models import SiteBanner
from pickem_superadmin.models import SuperAdminAuditLog


class OverviewTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.family = Family.objects.create(name='Dagostino', slug='dagostino')
        self.pool = Pool.objects.create(
            family=self.family, name='Pickem Pool', slug='pickem-pool', season=2627,
        )
        self.client.force_login(self.root)

    def test_overview_shows_counts(self):
        response = self.client.get(reverse('superadmin:overview'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['counts']['families'], 1)
        self.assertEqual(response.context['counts']['pools'], 1)

    def test_overview_flags_a_pool_with_no_settings_row(self):
        response = self.client.get(reverse('superadmin:overview'))
        self.assertIn(self.pool, response.context['anomalies']['pools_without_settings'])

    def test_overview_stops_flagging_once_settings_exist(self):
        PoolSettings.objects.create(pool=self.pool)
        response = self.client.get(reverse('superadmin:overview'))
        self.assertNotIn(self.pool, response.context['anomalies']['pools_without_settings'])

    def test_backfill_action_creates_the_settings_row(self):
        self.client.post(
            reverse('superadmin:pool_settings_backfill', args=[self.pool.id]),
        )
        self.assertTrue(PoolSettings.objects.filter(pool=self.pool).exists())

    def test_updating_the_current_season_audits(self):
        currentSeason.objects.create(season=2627, display_name='2026-2027')
        self.client.post(
            reverse('superadmin:season_update'),
            {'season': '2728', 'display_name': '2027-2028', 'confirm': '2728'},
        )
        self.assertEqual(currentSeason.objects.first().season, 2728)
        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.SEASON_UPDATED)
        self.assertEqual(entry.changes['season'], [2627, 2728])

    def test_season_update_requires_typed_confirmation(self):
        """get_season() drives the entire app. This is the highest-blast-radius
        field in the console, so it does not change on a stray click."""
        currentSeason.objects.create(season=2627, display_name='2026-2027')
        self.client.post(
            reverse('superadmin:season_update'),
            {'season': '2728', 'display_name': '2027-2028', 'confirm': 'wrong'},
        )
        self.assertEqual(currentSeason.objects.first().season, 2627)
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_publishing_a_site_wide_banner_leaves_family_null(self):
        """family=None is what makes a banner site-wide rather than one family's."""
        self.client.post(
            reverse('superadmin:banner_publish'),
            {'title': 'Scheduled maintenance Sunday', 'banner_type': 'warning'},
        )
        banner = SiteBanner.objects.get()
        self.assertIsNone(banner.family)
        self.assertTrue(banner.is_active)
        self.assertEqual(banner.title, 'Scheduled maintenance Sunday')

        entry = SuperAdminAuditLog.objects.get()
        self.assertEqual(entry.action, SuperAdminAuditLog.Action.BANNER_PUBLISHED)

    def test_publishing_a_banner_requires_a_title(self):
        self.client.post(reverse('superadmin:banner_publish'), {'title': ''})
        self.assertEqual(SiteBanner.objects.count(), 0)
        self.assertEqual(SuperAdminAuditLog.objects.count(), 0)

    def test_deactivating_a_banner_hides_it(self):
        banner = SiteBanner.objects.create(title='Old news', family=None)
        self.client.post(reverse('superadmin:banner_deactivate', args=[banner.id]))
        banner.refresh_from_db()
        self.assertFalse(banner.is_active)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin.tests.test_overview --settings=pickem.test_settings
```

Expected: FAIL — `KeyError: 'counts'` (the stub overview passes an empty context).

- [ ] **Step 3: Write the view**

Replace `pickem/pickem_superadmin/views/overview.py`:

```python
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from pickem_api.models import (
    Family, GamePicks, GamesAndScores, Pool, currentSeason, userSeasonPoints,
)
from pickem_superadmin import jobs, services
from pickem_superadmin.audit import diff_fields, log_action
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.models import SuperAdminAuditLog


def _anomalies(season):
    """Cheap checks that each point at something actionable. If a check cannot be
    made cheap, it does not belong on the landing page."""
    pools_without_settings = list(Pool.objects.filter(settings__isnull=True))

    stuck_games = list(
        GamesAndScores.objects.filter(
            gameStatus__icontains='progress',
            gameTime__lt=timezone.now() - timezone.timedelta(hours=6),
        )[:20]
    )

    families_without_members = list(
        Family.objects.annotate(
            active_members=Count('memberships', filter=Q(memberships__status='active')),
        ).filter(active_members=0)
    )

    pools_off_season = list(Pool.objects.exclude(season=season)) if season else []

    return {
        'pools_without_settings': pools_without_settings,
        'stuck_games': stuck_games,
        'families_without_members': families_without_members,
        'pools_off_season': pools_off_season,
    }


@superadmin_required
def overview(request):
    current = currentSeason.objects.first()
    season = current.season if current else None

    counts = {
        'families': Family.objects.count(),
        'families_inactive': Family.objects.filter(status=Family.Status.INACTIVE).count(),
        'pools': Pool.objects.count(),
        'users': User.objects.count(),
        'users_blocked': User.objects.filter(is_active=False).count(),
        'picks_this_season': (
            GamePicks.objects.filter(gameseason=season).count() if season else 0
        ),
    }

    return render(request, 'superadmin/overview.html', {
        'counts': counts,
        'health': jobs.scheduler_health(),
        'anomalies': _anomalies(season),
        'current_season': current,
    })


@superadmin_required
@require_POST
def pool_settings_backfill(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    services.backfill_pool_settings(request, pool)
    messages.success(request, f'Backfilled settings for {pool.family.slug}/{pool.slug}.')
    return redirect('superadmin:overview')


@superadmin_required
@require_POST
def season_update(request):
    """get_season() reads this and it drives the whole app — picks, standings,
    scores, stats. Highest blast radius in the console, so it takes a typed
    confirmation."""
    current = currentSeason.objects.first()
    if current is None:
        current = currentSeason.objects.create()

    try:
        new_season = int(request.POST.get('season', ''))
    except ValueError:
        messages.error(request, 'Season must be an integer in YYZZ format (e.g. 2627).')
        return redirect('superadmin:overview')

    if request.POST.get('confirm', '').strip() != str(new_season):
        messages.error(
            request,
            f'Confirmation did not match. Type "{new_season}" exactly to change the season.',
        )
        return redirect('superadmin:overview')

    before = {'season': current.season, 'display_name': current.display_name}
    current.season = new_season
    current.display_name = request.POST.get('display_name', '').strip()
    after = {'season': current.season, 'display_name': current.display_name}

    changes = diff_fields(before, after)
    if not changes:
        messages.success(request, 'No changes.')
        return redirect('superadmin:overview')

    current.save()
    log_action(
        request,
        action=SuperAdminAuditLog.Action.SEASON_UPDATED,
        target=current,
        summary=f'Current season set to {new_season}',
        changes=changes,
    )
    messages.success(request, f'Current season is now {new_season}.')
    return redirect('superadmin:overview')


@superadmin_required
@require_POST
def banner_publish(request):
    """Publish a site-wide banner. SiteBanner.family is nullable, and null is
    precisely what makes it site-wide rather than one family's."""
    title = request.POST.get('title', '').strip()
    if not title:
        messages.error(request, 'A banner needs a title.')
        return redirect('superadmin:overview')

    banner = SiteBanner.objects.create(
        title=title,
        description=request.POST.get('description', '').strip(),
        banner_type=request.POST.get('banner_type', 'info'),
        family=None,
        is_active=True,
    )
    log_action(
        request,
        action=SuperAdminAuditLog.Action.BANNER_PUBLISHED,
        target=banner,
        summary=f'Published site-wide banner: {title}',
        changes={'title': [None, title], 'is_active': [None, True]},
    )
    messages.success(request, 'Banner published site-wide.')
    return redirect('superadmin:overview')


@superadmin_required
@require_POST
def banner_deactivate(request, banner_id):
    banner = get_object_or_404(SiteBanner, pk=banner_id)
    banner.is_active = False
    banner.save(update_fields=['is_active', 'updated_at'])

    log_action(
        request,
        action=SuperAdminAuditLog.Action.BANNER_PUBLISHED,
        target=banner,
        summary=f'Deactivated banner: {banner.title}',
        changes={'is_active': [True, False]},
    )
    messages.success(request, 'Banner deactivated.')
    return redirect('superadmin:overview')
```

Add `SiteBanner` to the imports at the top of `overview.py`:

```python
from pickem_homepage.models import SiteBanner
```

and include the active site-wide banners in the `overview` view's context, so the template can list and deactivate them — add this to the `render` context dict:

```python
        'site_banners': SiteBanner.objects.filter(family__isnull=True, is_active=True),
```

Note: `_anomalies` references `GamesAndScores.gameStatus` and `.gameTime`. Confirm the real field names first:

```bash
cd pickem && sed -n 426,478p pickem_api/models.py
```

Use the model's actual status and kickoff-time field names. If the status values are not strings containing "progress", match on whatever the real values are — read `update_games.py` to see what it writes.

- [ ] **Step 4: Write the template**

Replace `pickem/pickem_superadmin/templates/superadmin/overview.html`:

```html
{% extends 'superadmin/base.html' %}
{% block title %}overview{% endblock %}
{% block heading %}Overview{% endblock %}
{% block content %}

  {% if not health.alive %}
    <div class="mb-4 border-l-4 border-red-600 bg-red-50 px-3 py-2 text-red-900">
      <strong>Pipeline is not running.</strong>
      {% if health.last_run %}
        Last execution {{ health.last_run|date:"Y-m-d H:i:s" }} ({{ health.last_status }}).
      {% else %}
        Nothing has ever executed.
      {% endif %}
      Scores, picks, and standings are going stale.
      <a href="{% url 'superadmin:jobs' %}" class="underline">Jobs &rarr;</a>
    </div>
  {% else %}
    <div class="mb-4 border-l-4 border-green-600 bg-green-50 px-3 py-2 text-green-900">
      Pipeline healthy — last run {{ health.last_run|date:"Y-m-d H:i:s" }} ({{ health.last_status }}).
    </div>
  {% endif %}

  <div class="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
    {% for label, value in counts.items %}
      <div class="border border-gray-300 bg-white px-3 py-2">
        <div class="font-mono text-lg">{{ value }}</div>
        <div class="text-gray-600">{{ label }}</div>
      </div>
    {% endfor %}
  </div>

  <h2 class="mb-1 font-semibold">Current season</h2>
  <form method="post" action="{% url 'superadmin:season_update' %}" class="mb-5 flex flex-wrap items-center gap-2">
    {% csrf_token %}
    <span class="text-gray-600">
      now: <span class="font-mono">{{ current_season.season|default:"unset" }}</span>
      ({{ current_season.display_name|default:"—" }})
    </span>
    <input type="text" name="season" placeholder="2728" class="w-24 border border-gray-300 px-2 py-1 font-mono">
    <input type="text" name="display_name" placeholder="2027-2028" class="w-32 border border-gray-300 px-2 py-1">
    <input type="text" name="confirm" placeholder="type the season to confirm"
           class="w-48 border border-red-400 px-2 py-1 font-mono">
    <button type="submit" class="border border-red-600 bg-red-600 px-3 py-1 text-white hover:bg-red-700">
      Change season
    </button>
    <span class="text-gray-500">drives get_season() everywhere — picks, scores, standings, stats</span>
  </form>

  <h2 class="mb-1 font-semibold">Site-wide banner</h2>
  <form method="post" action="{% url 'superadmin:banner_publish' %}" class="mb-2 flex flex-wrap items-center gap-2">
    {% csrf_token %}
    <input type="text" name="title" placeholder="banner message" class="w-72 border border-gray-300 px-2 py-1">
    <input type="text" name="description" placeholder="optional detail" class="w-72 border border-gray-300 px-2 py-1">
    <select name="banner_type" class="border border-gray-300 px-2 py-1">
      <option value="info">info</option>
      <option value="warning">warning</option>
      <option value="danger">danger</option>
      <option value="success">success</option>
    </select>
    <button type="submit" class="border border-gray-800 bg-gray-800 px-3 py-1 text-white hover:bg-gray-700">
      Publish site-wide
    </button>
  </form>
  <div class="mb-5 border border-gray-300 bg-white p-3">
    {% for banner in site_banners %}
      <form method="post" action="{% url 'superadmin:banner_deactivate' banner.id %}"
            class="flex items-center gap-2 py-0.5">
        {% csrf_token %}
        <span class="font-mono">[{{ banner.banner_type }}]</span>
        <span>{{ banner.title }}</span>
        <button type="submit" class="border border-gray-400 bg-white px-2 hover:bg-gray-50">deactivate</button>
      </form>
    {% empty %}
      <span class="text-gray-500">no active site-wide banners</span>
    {% endfor %}
  </div>

  <h2 class="mb-1 font-semibold">Anomalies</h2>

  <div class="mb-3 border border-gray-300 bg-white p-3">
    <div class="mb-1 font-semibold">
      Pools with no settings row
      <span class="font-mono text-gray-500">({{ anomalies.pools_without_settings|length }})</span>
    </div>
    {% for pool in anomalies.pools_without_settings %}
      <form method="post" action="{% url 'superadmin:pool_settings_backfill' pool.id %}"
            class="flex items-center gap-2 py-0.5">
        {% csrf_token %}
        <span class="font-mono">{{ pool.family.slug }}/{{ pool.slug }}</span>
        <button type="submit" class="border border-gray-400 bg-white px-2 hover:bg-gray-50">backfill</button>
      </form>
    {% empty %}
      <span class="text-gray-500">none</span>
    {% endfor %}
  </div>

  <div class="mb-3 border border-gray-300 bg-white p-3">
    <div class="mb-1 font-semibold">
      Games stuck in progress
      <span class="font-mono text-gray-500">({{ anomalies.stuck_games|length }})</span>
    </div>
    {% for game in anomalies.stuck_games %}
      <div class="font-mono">{{ game.slug }}</div>
    {% empty %}
      <span class="text-gray-500">none</span>
    {% endfor %}
  </div>

  <div class="mb-3 border border-gray-300 bg-white p-3">
    <div class="mb-1 font-semibold">
      Families with no active members
      <span class="font-mono text-gray-500">({{ anomalies.families_without_members|length }})</span>
    </div>
    {% for family in anomalies.families_without_members %}
      <div class="font-mono">{{ family.slug }}</div>
    {% empty %}
      <span class="text-gray-500">none</span>
    {% endfor %}
  </div>

  <div class="mb-3 border border-gray-300 bg-white p-3">
    <div class="mb-1 font-semibold">
      Pools not on the current season
      <span class="font-mono text-gray-500">({{ anomalies.pools_off_season|length }})</span>
    </div>
    {% for pool in anomalies.pools_off_season %}
      <div class="font-mono">{{ pool.family.slug }}/{{ pool.slug }} — {{ pool.season }}</div>
    {% empty %}
      <span class="text-gray-500">none</span>
    {% endfor %}
  </div>

{% endblock %}
```

- [ ] **Step 5: Wire URLs, views export, auth test**

`views/__init__.py`: add `pool_settings_backfill`, `season_update`, `banner_publish`, and `banner_deactivate` to the overview import and `__all__`.

`urls.py`: add

```python
    path('season/update/', views.season_update, name='season_update'),
    path('pools/<int:pool_id>/backfill-settings/', views.pool_settings_backfill, name='pool_settings_backfill'),
    path('banners/publish/', views.banner_publish, name='banner_publish'),
    path('banners/<int:banner_id>/deactivate/', views.banner_deactivate, name='banner_deactivate'),
```

`tests/test_auth.py`: add `('superadmin:season_update', [])`, `('superadmin:pool_settings_backfill', [1])`, `('superadmin:banner_publish', [])`, and `('superadmin:banner_deactivate', [1])` to `SUPERADMIN_POST_URLS`.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: PASS, zero failures.

- [ ] **Step 7: Rebuild Tailwind and commit**

```bash
npm run build:prod
git add pickem/pickem_superadmin pickem/pickem_homepage/static/css/tailwind.css
git commit -m "$(cat <<'EOF'
feat(superadmin): add overview with scheduler health and anomaly checks

Leads with pipeline health, because a dead scheduler is currently only
discoverable by noticing stale scores. Anomaly checks each link to the action
that fixes them. Changing the current season takes a typed confirmation — it
drives get_season() across the whole app. Also adds site-wide banner publishing
(SiteBanner with a null family).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Audit page

**Files:**
- Create: `pickem/pickem_superadmin/views/audit.py`, `templates/superadmin/audit.html`
- Modify: `pickem/pickem_superadmin/views/__init__.py`, `urls.py`, `base.html`, `tests/test_auth.py`, `tests/test_audit.py`

**Interfaces:**
- Consumes: `SuperAdminAuditLog`, `FamilyAuditLog`.
- Produces: URL name `superadmin:audit` (GET).

- [ ] **Step 1: Write the failing test**

Append to `pickem/pickem_superadmin/tests/test_audit.py`:

```python
from django.urls import reverse


class AuditPageTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.client.force_login(self.root)

    def test_page_lists_superadmin_entries_with_before_after(self):
        SuperAdminAuditLog.objects.create(
            actor=self.root,
            action=SuperAdminAuditLog.Action.USER_BLOCKED,
            target_type='User', target_id='7',
            summary='Blocked user spammer',
            changes={'is_active': [True, False]},
        )
        response = self.client.get(reverse('superadmin:audit'))
        self.assertContains(response, 'Blocked user spammer')
        self.assertContains(response, 'is_active')

    def test_filtering_by_action_narrows_the_list(self):
        SuperAdminAuditLog.objects.create(
            actor=self.root, action=SuperAdminAuditLog.Action.USER_BLOCKED,
            summary='blocked someone',
        )
        SuperAdminAuditLog.objects.create(
            actor=self.root, action=SuperAdminAuditLog.Action.TEAM_UPDATED,
            summary='touched a team',
        )
        response = self.client.get(
            reverse('superadmin:audit'), {'action': SuperAdminAuditLog.Action.USER_BLOCKED},
        )
        self.assertContains(response, 'blocked someone')
        self.assertNotContains(response, 'touched a team')
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pickem && python manage.py test pickem_superadmin.tests.test_audit --settings=pickem.test_settings
```

Expected: FAIL — `NoReverseMatch: 'superadmin:audit'`.

- [ ] **Step 3: Write the view**

`pickem/pickem_superadmin/views/audit.py`:

```python
from django.core.paginator import Paginator
from django.shortcuts import render

from pickem_api.models import FamilyAuditLog
from pickem_superadmin.decorators import superadmin_required
from pickem_superadmin.models import SuperAdminAuditLog


@superadmin_required
def audit(request):
    entries = SuperAdminAuditLog.objects.select_related('actor')

    action = request.GET.get('action', '').strip()
    actor = request.GET.get('actor', '').strip()
    if action:
        entries = entries.filter(action=action)
    if actor:
        entries = entries.filter(actor__username__icontains=actor)

    # Every family's own audit log in one stream — today this is readable only
    # one family at a time.
    family_entries = Paginator(
        FamilyAuditLog.objects.select_related('family', 'pool', 'actor')
        .order_by('-created_at'),
        25,
    ).get_page(request.GET.get('family_page'))

    return render(request, 'superadmin/audit.html', {
        'entries': Paginator(entries, 50).get_page(request.GET.get('page')),
        'family_entries': family_entries,
        'actions': SuperAdminAuditLog.Action.choices,
        'action_filter': action,
        'actor_filter': actor,
    })
```

- [ ] **Step 4: Write the template**

`pickem/pickem_superadmin/templates/superadmin/audit.html`:

```html
{% extends 'superadmin/base.html' %}
{% block title %}audit{% endblock %}
{% block heading %}Audit{% endblock %}
{% block content %}

  <form method="get" class="mb-3 flex gap-2">
    <select name="action" class="border border-gray-300 px-2 py-1">
      <option value="">all actions</option>
      {% for value, label in actions %}
        <option value="{{ value }}" {% if action_filter == value %}selected{% endif %}>{{ label }}</option>
      {% endfor %}
    </select>
    <input type="text" name="actor" value="{{ actor_filter }}" placeholder="actor username"
           class="border border-gray-300 px-2 py-1">
    <button type="submit" class="border border-gray-400 bg-white px-2 py-1 hover:bg-gray-50">filter</button>
  </form>

  <h2 class="mb-1 font-semibold">Superadmin actions</h2>
  <div class="mb-5 overflow-x-auto border border-gray-300 bg-white">
    <table class="w-full border-collapse">
      <thead class="bg-gray-200 text-left">
        <tr>
          <th class="px-2 py-1 font-semibold">when</th>
          <th class="px-2 py-1 font-semibold">actor</th>
          <th class="px-2 py-1 font-semibold">action</th>
          <th class="px-2 py-1 font-semibold">summary</th>
          <th class="px-2 py-1 font-semibold">before &rarr; after</th>
          <th class="px-2 py-1 font-semibold">ip</th>
        </tr>
      </thead>
      <tbody>
        {% for entry in entries %}
          <tr class="border-t border-gray-200 align-top">
            <td class="px-2 py-1 font-mono">{{ entry.created_at|date:"Y-m-d H:i:s" }}</td>
            <td class="px-2 py-1 font-mono">{{ entry.actor.username|default:"—" }}</td>
            <td class="px-2 py-1">{{ entry.get_action_display }}</td>
            <td class="px-2 py-1">{{ entry.summary }}</td>
            <td class="px-2 py-1 font-mono text-gray-700">
              {% for field, pair in entry.changes.items %}
                <div>{{ field }}: {{ pair.0|default_if_none:"∅" }} &rarr; {{ pair.1|default_if_none:"∅" }}</div>
              {% endfor %}
            </td>
            <td class="px-2 py-1 font-mono text-gray-600">{{ entry.ip_address|default:"—" }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  {% if entries.has_other_pages %}
    <div class="mb-5 flex gap-2">
      {% if entries.has_previous %}
        <a href="?page={{ entries.previous_page_number }}" class="underline">&larr; prev</a>
      {% endif %}
      <span class="text-gray-600">page {{ entries.number }} of {{ entries.paginator.num_pages }}</span>
      {% if entries.has_next %}
        <a href="?page={{ entries.next_page_number }}" class="underline">next &rarr;</a>
      {% endif %}
    </div>
  {% endif %}

  <h2 class="mb-1 font-semibold">All families' audit logs</h2>
  <div class="overflow-x-auto border border-gray-300 bg-white">
    <table class="w-full border-collapse">
      <thead class="bg-gray-200 text-left">
        <tr>
          <th class="px-2 py-1 font-semibold">when</th>
          <th class="px-2 py-1 font-semibold">family</th>
          <th class="px-2 py-1 font-semibold">actor</th>
          <th class="px-2 py-1 font-semibold">action</th>
          <th class="px-2 py-1 font-semibold">metadata</th>
        </tr>
      </thead>
      <tbody>
        {% for entry in family_entries %}
          <tr class="border-t border-gray-200 align-top">
            <td class="px-2 py-1 font-mono">{{ entry.created_at|date:"Y-m-d H:i:s" }}</td>
            <td class="px-2 py-1 font-mono">{{ entry.family.slug }}</td>
            <td class="px-2 py-1 font-mono">{{ entry.actor.username|default:"—" }}</td>
            <td class="px-2 py-1">{{ entry.get_action_display }}</td>
            <td class="px-2 py-1 font-mono text-gray-600">{{ entry.metadata }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  {% if family_entries.has_other_pages %}
    <div class="mt-2 flex gap-2">
      {% if family_entries.has_previous %}
        <a href="?family_page={{ family_entries.previous_page_number }}" class="underline">&larr; prev</a>
      {% endif %}
      <span class="text-gray-600">page {{ family_entries.number }} of {{ family_entries.paginator.num_pages }}</span>
      {% if family_entries.has_next %}
        <a href="?family_page={{ family_entries.next_page_number }}" class="underline">next &rarr;</a>
      {% endif %}
    </div>
  {% endif %}

{% endblock %}
```

- [ ] **Step 5: Wire URLs, views export, nav, auth test**

`views/__init__.py`: add `from pickem_superadmin.views.audit import audit`, extend `__all__`.

`urls.py`: add `path('audit/', views.audit, name='audit'),`

`base.html` nav: add the `audit` link.

`tests/test_auth.py`: add `'superadmin:audit'` to `SUPERADMIN_URLS`.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd pickem && python manage.py test pickem_superadmin --settings=pickem.test_settings
```

Expected: PASS, zero failures.

- [ ] **Step 7: Rebuild Tailwind and commit**

```bash
npm run build:prod
git add pickem/pickem_superadmin pickem/pickem_homepage/static/css/tailwind.css
git commit -m "$(cat <<'EOF'
feat(superadmin): add global audit page

Superadmin actions with before/after diffs, filterable by actor and action, plus
every family's audit log in one stream — today readable only one family at a time.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Final verification

**Files:**
- Modify: `CLAUDE.md` (document the console), `TODO.md` (already ticked in Task 7)

- [ ] **Step 1: Run the whole suite**

```bash
rm -rf /tmp/django_cache
cd pickem && python manage.py test --settings=pickem.test_settings
```

Expected: PASS, zero failures — roughly 260 existing tests (minus the `job_runs` ones removed in Task 8) plus ~80 new. If anything fails, fix it — do not proceed.

- [ ] **Step 2: Verify the migrations apply cleanly from scratch**

```bash
cd pickem && python manage.py makemigrations --check --dry-run
```

Expected: `No changes detected`. If it wants to create a migration, one was missed in Task 2 or 3 — generate and commit it.

- [ ] **Step 3: Drive the console in a real browser**

The dev server is already running at `http://localhost:8000` against the restored production DB. **Do not mutate real data** — read-only checks only, plus a block/unblock on a user you create yourself.

Verify by hand:
1. `/superadmin/` as a superuser → 200, counts populate, scheduler health renders.
2. Log in as a non-superuser → `/superadmin/` returns 404, not 403, not a redirect.
3. `/superadmin/pools/` → the matrix renders, horizontal scroll works, the sticky first column stays put, `pick_type` and `include_playoffs` are visibly disabled.
4. `/superadmin/teams/` → preview swatches render.
5. `/superadmin/jobs/` → scheduler health is accurate; if a scheduler is alive, queue `update_records` and confirm it appears in the history within ~60s.

- [ ] **Step 4: Document the console in CLAUDE.md**

Add to `CLAUDE.md` after the "Authentication & Authorization" section:

```markdown
### Superadmin Console

Superuser-only cross-family operator console at `/superadmin/` (app: `pickem_superadmin`).

- **Gate**: `@superadmin_required` (`pickem_superadmin/decorators.py`) — `is_superuser` only; non-superusers get 404, not 403. Anonymous users hit `RequireLoginForInternalPagesMiddleware` first and get a login redirect.
- **Pages**: overview (scheduler health + anomaly checks + current season), families, pools (cross-family settings matrix), users (site-wide block/unblock), teams (`logo_contrast_preset` + live preview), jobs (queue pipeline runs), audit.
- **Audit**: every write goes through `log_action()` (`pickem_superadmin/audit.py`), which writes a `SuperAdminAuditLog` row with a before/after diff and dual-writes `FamilyAuditLog` for family-scoped actions.
- **Jobs are queued, not run inline** — a one-off job goes into the APScheduler `DjangoJobStore` and the scheduler process (`RUN_SCHEDULER=true`) executes it within ~60s. Commands are allowlisted in `pickem_superadmin/jobs.QUEUEABLE_COMMANDS`.
- **`pick_type=against_spread` and `include_playoffs` are locked** here and in `FamilyAdminSettingsForm` — unimplemented downstream, not permission-gated. Unlock both together when the backend lands.
- Django admin (`/admin/`) remains the raw-CRUD escape hatch.
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: document the superadmin console in CLAUDE.md

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```
