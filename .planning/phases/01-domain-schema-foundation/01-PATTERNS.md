# Phase 1: Domain Schema Foundation - Pattern Map

**Mapped:** 2026-06-28
**Files analyzed:** 11 target files, 9 analog/source files
**Analogs found:** 8 / 8 target implementation areas

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pickem/pickem_api/models.py` | model | CRUD | `UserProfile`, `GamePicks`, `userSeasonPoints`, `userStats` in `pickem/pickem_api/models.py` | exact |
| `pickem/pickem_homepage/models.py` | model | CRUD/event-derived counters | `SiteBanner`, `MessageBoardPost`, `MessageBoardComment`, `MessageBoardVote` in `pickem/pickem_homepage/models.py` | exact |
| `pickem/pickem_api/migrations/0073_*.py` | migration | schema transform | `pickem/pickem_api/migrations/0062_add_userprofile_model.py`, `0068_userprofile_is_commissioner.py` | exact |
| `pickem/pickem_homepage/migrations/0005_*.py` | migration | schema transform | `pickem/pickem_homepage/migrations/0004_messageboardpost_messageboardcomment_and_more.py` | exact |
| `pickem/pickem_api/migrations/0074_*.py` or same migration | migration | batch backfill | `MIGRATION_PLAN.md` safe migration steps plus Django `RunPython` conventions | partial |
| `pickem/pickem_api/admin.py` | config/admin | CRUD | `UserProfileAdmin`, `GamePicksAdmin`, `currentSeasonAdmin` in `pickem/pickem_api/admin.py` | exact |
| `pickem/pickem_homepage/admin.py` | config/admin | CRUD | `SiteBannerAdmin`, `MessageBoardPostAdmin`, `MessageBoardVoteAdmin` in `pickem/pickem_homepage/admin.py` | exact |
| `pickem/pickem_api/tests.py` | test | CRUD/transform | existing model and serializer tests in `pickem/pickem_api/tests.py` | exact |
| `pickem/pickem_homepage/tests.py` | test | request-response/CRUD/system-check | existing smoke, helper, model, and system-check tests in `pickem/pickem_homepage/tests.py` | exact |

## Pattern Assignments

### `pickem/pickem_api/models.py` (model, CRUD)

**Analog:** `pickem/pickem_api/models.py`

**Imports pattern** (lines 1-5):
```python
from time import timezone
import uuid
from xmlrpc.client import Boolean
from django.db import models
from django.contrib.auth.models import User
```

Use the existing direct `User` import style for new domain FKs unless the executor intentionally modernizes a migration-only reference with `settings.AUTH_USER_MODEL`. Avoid relying on the unused/bad imports for new code; they are legacy noise, not a pattern to copy.

**User-owned model pattern** (lines 10-36):
```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    tagline = models.CharField(max_length=200, blank=True, null=True, help_text="A short personal tagline or bio")
    email_notifications = models.BooleanField(default=True, help_text="Receive email notifications")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        ordering = ['user__username']
```

Copy this for new first-class domain models: explicit `created_at` / `updated_at`, helpful `help_text`, readable `__str__`, and `Meta` with `verbose_name`, `verbose_name_plural`, and deterministic `ordering`.

**Tenant FK extension targets** (lines 104-123, 126-213, 311-341):
```python
class GamePicks(models.Model):
    id = models.CharField(max_length=250, primary_key=True)
    userEmail = models.EmailField(blank=True, db_column='useremail')
    uid = models.IntegerField(blank=True, null=True)
    userID = models.CharField(max_length=250, blank=True, db_column='userid')
    gameseason = models.IntegerField(blank=True, null=True)
    pick_game_id = models.IntegerField(blank=True)
    pickAdded = models.DateTimeField(auto_now_add=True, db_column='pickadded')
    pickUpdated = models.DateTimeField(auto_now=True, db_column='pickupdated')

    class Meta:
        ordering = ['gameWeek']
```

```python
class userSeasonPoints(models.Model):
    id = models.AutoField(primary_key=True)
    userEmail = models.EmailField(blank=True, db_column='useremail')
    userID = models.CharField(max_length=250, blank=True, db_column='userid')
    gameseason = models.IntegerField(blank=True, null=True)
    total_points = models.IntegerField(blank=True, null=True)
    current_rank = models.IntegerField(blank=True, null=True, help_text='Current ranking position (handles ties)')

    class Meta:
        ordering = ['total_points']
```

```python
class userStats(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    userEmail = models.EmailField(blank=True, db_column='useremail')
    userID = models.CharField(max_length=250, blank=True, db_column='userid')
```

Add `pool = models.ForeignKey(..., blank=True, null=True, on_delete=models.SET_NULL, related_name=...)` to tenant-owned competition data in Phase 1. Keep fields nullable per D-11 and `MIGRATION_PLAN.md`; do not make tenant FKs non-null yet.

**Global reference data to leave unscoped** (lines 39-101, 305-309):
```python
class Teams(models.Model):
    id = models.IntegerField(primary_key=True)
    gameseason = models.IntegerField(blank=True, null=True)
    teamNameSlug = models.CharField(max_length=250, db_column='teamnameslug')

class GamesAndScores(models.Model):
    id = models.IntegerField(primary_key=True)
    slug = models.SlugField(max_length=250)
    competition = models.CharField(max_length=250)
    gameseason = models.IntegerField(blank=True, null=True)

class GameWeeks(models.Model):
    weekNumber = models.IntegerField(db_column='weeknumber')
    competition = models.CharField(max_length=250)
    date = models.DateField()
    season = models.IntegerField(blank=True, null=True)
```

Do not add `family` or `pool` to `Teams`, `GamesAndScores`, or `GameWeeks` in Phase 1.

### `pickem/pickem_homepage/models.py` (model, CRUD/event-derived counters)

**Analog:** `pickem/pickem_homepage/models.py`

**Imports pattern** (lines 1-3):
```python
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
```

**Banner model pattern** (lines 5-83):
```python
class SiteBanner(models.Model):
    title = models.CharField(max_length=200, help_text="Banner title/message")
    description = models.TextField(blank=True, help_text="Optional additional description")
    is_active = models.BooleanField(default=True, help_text="Whether this banner should be displayed")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = "Site Banner"
        verbose_name_plural = "Site Banners"
```

If scoping banners, prefer `family = models.ForeignKey(..., blank=True, null=True, on_delete=models.SET_NULL, related_name='banners')` so site-wide banners remain possible.

**Message board model pattern** (lines 86-121, 124-161):
```python
class MessageBoardPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=200, help_text="Post title")
    content = models.TextField(help_text="Post content")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_pinned = models.BooleanField(default=False, help_text="Pin this post to the top")
    is_active = models.BooleanField(default=True, help_text="Hide/show this post")

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = "Message Board Post"
        verbose_name_plural = "Message Board Posts"
```

```python
class MessageBoardComment(models.Model):
    post = models.ForeignKey(MessageBoardPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
```

Add `family` to posts. Comments can inherit through `post`, but Phase 1 may add explicit nullable `family` on comments for backfill/query simplicity if the implementation keeps it synchronized later.

**Vote uniqueness anti-pattern to fix or avoid extending** (lines 164-185):
```python
class MessageBoardVote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(MessageBoardPost, on_delete=models.CASCADE, null=True, blank=True, related_name='votes')
    comment = models.ForeignKey(MessageBoardComment, on_delete=models.CASCADE, null=True, blank=True, related_name='votes')

    class Meta:
        unique_together = [
            ['user', 'post'],
            ['user', 'comment'],
        ]
```

Do not copy this loose dual-null target design for new models. `DISCOVERY.md` flags that it lacks a check requiring exactly one target. If Phase 1 touches votes for family scoping, add only the tenant FK/backfill unless the plan explicitly includes a safe check constraint with existing-data validation.

### `pickem/pickem_api/migrations/0073_*.py` (migration, schema transform)

**Analogs:** `pickem/pickem_api/migrations/0062_add_userprofile_model.py`, `0068_userprofile_is_commissioner.py`

**Dependency pattern** (0062 lines 3-13):
```python
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('pickem_api', '0061_currentseason'),
    ]
```

For new API schema migration, depend on current API head `('pickem_api', '0072_rename_statustype_column')` and include `migrations.swappable_dependency(settings.AUTH_USER_MODEL)` for FKs to auth users. If API migrations reference homepage models directly, add a cross-app dependency on the relevant homepage migration head.

**CreateModel pattern** (0062 lines 16-35):
```python
migrations.CreateModel(
    name='UserProfile',
    fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('tagline', models.CharField(blank=True, help_text='A short personal tagline or bio', max_length=200, null=True)),
        ('created_at', models.DateTimeField(auto_now_add=True)),
        ('updated_at', models.DateTimeField(auto_now=True)),
        ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
    ],
    options={
        'verbose_name': 'User Profile',
        'verbose_name_plural': 'User Profiles',
        'ordering': ['user__username'],
    },
)
```

Use generated Django migrations for `Family`, `FamilyMembership`, `Pool`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog`. Prefer explicit constraints/indexes in `Meta` so migrations generate `AddConstraint`/`AddIndex` rather than ad hoc SQL.

**AddField pattern** (0068 lines 8-17):
```python
dependencies = [
    ('pickem_api', '0067_currentseason_display_name'),
]

operations = [
    migrations.AddField(
        model_name='userprofile',
        name='is_commissioner',
        field=models.BooleanField(default=False, help_text='User has commissioner privileges'),
    ),
]
```

For tenant FK additions to existing large/important tables, follow this pattern but make them nullable: `blank=True, null=True`. Do not add defaults that would force a table rewrite or hide missing backfill.

### `pickem/pickem_homepage/migrations/0005_*.py` (migration, schema transform)

**Analog:** `pickem/pickem_homepage/migrations/0004_messageboardpost_messageboardcomment_and_more.py`

**Cross-user dependency and model creation pattern** (lines 3-13, 16-35):
```python
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

dependencies = [
    migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ('pickem_homepage', '0003_initial'),
]
```

Homepage migration head is currently `('pickem_homepage', '0004_messageboardpost_messageboardcomment_and_more')`. If homepage `family` FKs point to `pickem_api.Family`, this migration must depend on the API migration that creates `Family`.

**Existing community FK style** (lines 46-49, 62-64):
```python
('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='pickem_homepage.messageboardcomment')),
('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='pickem_homepage.messageboardpost')),
('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to=settings.AUTH_USER_MODEL)),
```

Use string app-label model references in generated migrations. For nullable tenant FKs, use `on_delete=django.db.models.deletion.SET_NULL` unless the product wants tenant deletion to cascade community history.

### Legacy data migration (migration, batch backfill)

**Analog:** `MIGRATION_PLAN.md`

**Safe steps to implement** (`MIGRATION_PLAN.md`, "Safe Migration Steps"):
```text
2. Add schema, nullable first.
   - Add new family/pool/membership/invite/audit tables.
   - Add nullable tenant FKs to existing tenant-owned tables.
   - Add indexes that do not require non-null data.

3. Backfill default family/pool.
   - Create legacy family and pool idempotently.
   - Create memberships from active users and referenced records.
   - Map commissioners to owner/admin roles.
   - Set tenant FK on all existing rows.
```

Implement backfill with `migrations.RunPython(forwards, backwards)` using `apps.get_model(...)`, not direct model imports. Use `get_or_create` / `update_or_create` keyed by deterministic slugs:

```python
Family = apps.get_model('pickem_api', 'Family')
Pool = apps.get_model('pickem_api', 'Pool')
FamilyMembership = apps.get_model('pickem_api', 'FamilyMembership')
User = apps.get_model('auth', 'User')

legacy_family, _ = Family.objects.get_or_create(
    slug='legacy-family-league',
    defaults={'name': 'Legacy Family League', 'created_by': owner},
)
legacy_pool, _ = Pool.objects.get_or_create(
    family=legacy_family,
    slug='legacy-pickem',
    defaults={'name': 'Legacy Pickem', 'season': season, 'competition': 'nfl'},
)
```

Backfill with bulk `update()` where possible:

```python
GamePicks.objects.filter(pool__isnull=True).update(pool=legacy_pool)
userSeasonPoints.objects.filter(pool__isnull=True).update(pool=legacy_pool)
userPoints.objects.filter(pool__isnull=True).update(pool=legacy_pool)
userStats.objects.filter(pool__isnull=True).update(pool=legacy_pool)
```

For memberships, account for both real users and denormalized references. Existing records use `uid`, `userEmail`, and `userID`; some may not resolve to active users. Do not fail the migration on deleted/missing users. Create memberships only for resolvable `auth.User` rows and document skipped references.

### `pickem/pickem_api/admin.py` (config/admin, CRUD)

**Analog:** `pickem/pickem_api/admin.py`

**Import and register pattern** (lines 1-7):
```python
from django.contrib import admin
from .models import GamePicks, GamesAndScores, GameWeeks, Teams, userPoints, userSeasonPoints, userStats, currentSeason, UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'tagline', 'favorite_team', 'phone_number', 'email_notifications', 'dark_mode', 'private_profile', 'is_commissioner', 'created_at', 'updated_at')
```

Add new API models to the `.models import ...` list and register each with `@admin.register`.

**Fieldset pattern for richer models** (lines 14-31):
```python
fieldsets = (
    ('User Information', {
        'fields': ('user',)
    }),
    ('Personal Information', {
        'fields': ('tagline', 'favorite_team', 'phone_number')
    }),
    ('Metadata', {
        'fields': ('created_at', 'updated_at'),
        'classes': ('collapse',)
    }),
)
```

Use fieldsets for `Family`, `Pool`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog`. Put timestamps and audit metadata in collapsed/read-only sections.

**List/search/date pattern** (lines 42-49, 91-102):
```python
@admin.register(GamePicks)
class GamesPicksAdmin(admin.ModelAdmin):
    list_display = ('userEmail', 'uid', 'slug', 'competition', 'gameseason', 'gameWeek', 'gameyear', 'pick_game_id', 'pick', 'pick_correct', 'tieBreakerScore', 'tieBreakerYards', 'pickAdded', 'pickUpdated')
    list_filter = ('userEmail', 'gameseason', 'gameWeek', 'gameyear')
    search_fields = ('userEmail',)
    date_hierarchy = 'pickAdded'
    ordering = ('pickAdded',)
```

For tenant models, include `family`, `pool`, `role`, `status`, `season`, and timestamp fields in `list_display` / `list_filter` as applicable. Add `readonly_fields` for generated hashes, counters, and timestamps.

### `pickem/pickem_homepage/admin.py` (config/admin, CRUD)

**Analog:** `pickem/pickem_homepage/admin.py`

**Admin utility import pattern** (lines 1-4):
```python
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import SiteBanner, MessageBoardPost, MessageBoardComment, MessageBoardVote
```

**List/fields/read-only pattern** (lines 63-81):
```python
@admin.register(MessageBoardPost)
class MessageBoardPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'score_display', 'comment_count', 'is_pinned', 'is_active', 'created_at']
    list_filter = ['is_pinned', 'is_active', 'created_at', 'user']
    search_fields = ['title', 'content', 'user__username']
    ordering = ['-is_pinned', '-created_at']
    readonly_fields = ['upvotes', 'downvotes', 'created_at', 'updated_at']
```

When adding `family` to community models/admin, add it to `list_display`, `list_filter`, and `fields`; keep vote counters read-only.

**Computed display pattern** (lines 83-98, 177-188):
```python
def score_display(self, obj):
    score = obj.score
    if score > 0:
        return format_html('<span style="color: green; font-weight: bold;">+{}</span>', score)
    elif score < 0:
        return format_html('<span style="color: red; font-weight: bold;">{}</span>', score)
    else:
        return format_html('<span style="color: gray;">0</span>')

score_display.short_description = 'Score'
score_display.admin_order_field = 'upvotes'
```

Use this style for status displays (`active`, `revoked`, `expired`) if useful, but avoid non-ASCII icons in new admin output unless already present in the target method.

### `pickem/pickem_api/tests.py` (test, CRUD/transform)

**Analog:** `pickem/pickem_api/tests.py`

**Imports and TestCase style** (lines 1-11):
```python
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from pickem_api.models import (
    UserProfile, Teams, GamesAndScores, GamePicks,
    userSeasonPoints, GameWeeks, userStats, currentSeason,
)
```

Extend this import tuple with new domain models. Keep tests as Django `TestCase` classes with explicit fixture creation.

**Fixture setup pattern** (lines 14-31):
```python
class UserProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_create_profile(self):
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(profile.user, self.user)
```

For new domain models, use small `setUp` or `setUpTestData` fixtures: create user, family, membership, pool, and settings. Assert defaults, `__str__`, uniqueness constraints, invite hash behavior, and nullable tenant FK compatibility on existing models.

**Minimal model assertions pattern** (lines 68-82, 93-97):
```python
class GamePicksModelTest(TestCase):
    def test_create_pick(self):
        pick = GamePicks.objects.create(
            id='pick-1', pick_game_id=100,
        )
        self.assertEqual(pick.id, 'pick-1')
        self.assertFalse(pick.pick_correct)
```

Add focused tests proving `GamePicks`, `userSeasonPoints`, `userPoints`, and `userStats` can be created with and without `pool` during Phase 1.

### `pickem/pickem_homepage/tests.py` (test, request-response/CRUD/system-check)

**Analog:** `pickem/pickem_homepage/tests.py`

**Shared fixture pattern** (lines 19-31, 81-90):
```python
class ViewSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.client = Client()
```

If tests touch views/system checks, keep `Site` and `currentSeason` setup. For pure model tests, create only the users/family/post records needed.

**Model property test pattern** (lines 148-182, 185-215, 217-267):
```python
class MessageBoardPostModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("poster", password="pass")

    def test_str(self):
        post = MessageBoardPost.objects.create(
            user=self.user, title="Hello World", content="body"
        )
        self.assertEqual(str(post), "Hello World by poster")
```

Add tests proving `MessageBoardPost.family`, optional `MessageBoardComment.family`, vote family behavior if added, and `SiteBanner.family` nullable/site-wide behavior.

**System check pattern** (lines 270-276):
```python
class DjangoSystemCheckTests(TestCase):
    def test_django_system_check(self):
        out = StringIO()
        call_command("check", stdout=out, stderr=StringIO())
        # If check passes, no exception is raised
```

Keep or extend this as a cheap safety net after schema/admin changes.

## Shared Patterns

### Model Field Style And Naming

**Sources:** `pickem/pickem_api/models.py`, `pickem/pickem_homepage/models.py`

- Existing legacy fields often use camelCase Python names plus `db_column` for lowercase DB columns, e.g. `teamNameSlug = models.CharField(..., db_column='teamnameslug')` at `models.py` lines 42-49.
- New domain models should use conventional snake_case (`created_by`, `role_to_grant`, `expires_at`, `code_hash`) because they are new tables and do not need legacy column compatibility.
- Existing timestamp convention is `created_at` / `updated_at` for newer models and legacy names like `pickAdded` / `playerUpdated` only on old tables. Use `created_at` / `updated_at` for new models.
- Use `blank=True, null=True` for transitional tenant FKs. This is explicitly required by D-11.
- Use readable `related_name` values on new FKs; existing examples include `related_name='profile'`, `related_name='posts'`, `related_name='comments'`, and `related_name='votes'`.

### Migration Dependencies

**Sources:** migration heads and required migrations

- Current API head: `pickem_api/migrations/0072_rename_statustype_column.py`.
- Current homepage head: `pickem_homepage/migrations/0004_messageboardpost_messageboardcomment_and_more.py`.
- API schema migration should create `Family`/`Pool` before homepage migration adds FKs to `Family`.
- Homepage migration adding `family` must depend on the API migration containing `Family`.
- Backfill migration must depend on both apps' schema migrations if it writes both API and homepage tenant fields.
- Use `migrations.swappable_dependency(settings.AUTH_USER_MODEL)` where migration models reference users, matching `0062` and homepage `0004`.

### Admin Conventions

**Sources:** `pickem/pickem_api/admin.py`, `pickem/pickem_homepage/admin.py`

- Register models with `@admin.register(Model)`.
- Use `list_display`, `list_filter`, `search_fields`, `ordering`, and `date_hierarchy` where date fields exist.
- Use `readonly_fields` for timestamps and derived/generated fields.
- Richer admin classes use `fieldsets`; community admin uses explicit `fields` lists.

### Test Conventions

**Sources:** `pickem/pickem_api/tests.py`, `pickem/pickem_homepage/tests.py`

- Use Django `TestCase`.
- Create users with `User.objects.create_user(...)` and superusers with `User.objects.create_superuser(...)`.
- Prefer direct ORM creation and simple assertions over factories; no factory library is present.
- Use `setUpTestData` for class-wide fixtures and `setUp` for per-test client setup.
- Include `call_command("check")` system-check coverage after schema/admin changes.

### Existing Anti-Patterns To Avoid During Phase 1

**Sources:** `DISCOVERY.md`, current models/admin/tests

- Do not make tenant FKs non-null in Phase 1; add nullable fields, backfill, and defer enforcement.
- Do not tenant-scope global NFL reference data (`GamesAndScores`, `GameWeeks`, `Teams`).
- Do not drop denormalized legacy user fields (`userEmail`, `uid`, `userID`) yet.
- Do not use raw invite codes at rest; store only `code_hash`.
- Do not copy the `MessageBoardVote` dual-null target shape for new models without a check constraint.
- Do not add strict tenant-scoped uniqueness before checking for duplicate legacy rows.
- Do not broad-refactor large views/templates/routes in this schema phase.
- Do not fail the legacy backfill when denormalized user references cannot be resolved to active `auth.User` rows.
- Do not add defaults to tenant FKs that mask missing backfill or cause expensive rewrites.

## No Analog Found

| File/Area | Role | Data Flow | Reason |
|-----------|------|-----------|--------|
| Legacy tenant data migration | migration | batch backfill | Existing migrations shown are schema-only; use Django `RunPython` best practice plus `MIGRATION_PLAN.md`. |
| Invitation hashing helpers | utility/model method | transform | No existing hash-at-rest invite/token model exists in this codebase. Use Django crypto/hash utilities in implementation plan. |
| Audit log model | model | event-driven append-only | No existing append-only audit/event model exists; use standard Django model patterns from `UserProfile` plus JSON metadata. |

## Metadata

**Analog search scope:** `pickem/pickem_api`, `pickem/pickem_homepage`, phase/discovery migration docs
**Files scanned:** 16
**Pattern extraction date:** 2026-06-28
**Dirty worktree note:** Existing modified/untracked files were observed and not changed. This artifact is the only file written.
