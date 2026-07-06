# Phase 03 Patterns: Onboarding And Family Selection

Mapped: 2026-06-29

## Closest Existing Patterns

| Target area | Role | Data flow | Closest analog | Match quality |
|---|---|---|---|---|
| Post-login/root membership router | view | request-response | `pickem/pickem_homepage/views.py` lines 57-289, 690-699 | role-match |
| Create family + default pool | view/helper | CRUD | `pickem/pickem_homepage/views.py` lines 702-791; `pickem/pickem_api/models.py` lines 39-184 | role-match |
| Join by invite | view/helper | CRUD + request-response | `pickem/pickem_homepage/views.py` lines 1211-1317; `pickem/pickem_api/models.py` lines 185-230 | role-match |
| Owner-created minimal invite | view/helper | CRUD + transient-secret response | `pickem/pickem_api/models.py` lines 185-230; `pickem/pickem_api/tests.py` lines 138-160 | partial exact |
| Family/pool route guard | middleware/decorator | request-response | `pickem/pickem_homepage/authz.py` lines 16-40 | exact |
| Active family switcher data | helper/context | request-response | `pickem/pickem_api/authz.py` lines 198-204 | exact |
| Header/nav integration | template | request-response | `pickem/pickem_homepage/templates/pickem/base.html` lines 117-236, 342-438 | exact |
| Onboarding/empty state UI | template | request-response | `pickem/pickem_homepage/templates/pickem/home.html` lines 24-45; `base.html` lines 284-332 | role-match |
| Route tests | test | request-response | `pickem/pickem_homepage/tests.py` lines 27-87, 131-207 | exact |
| Model/authz/invite tests | test | CRUD + authz denial | `pickem/pickem_api/tests.py` lines 52-160, 212-370 | exact |

Copy these conventions:

```python
# pickem/pickem_homepage/views.py:702-791
@login_required
def profile(request):
    gameseason = get_season()
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    ...
    if request.method == 'POST':
        ...
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    return render(request, 'pickem/profile.html', context)
```

```python
# pickem/pickem_homepage/authz.py:16-34
def family_member_required(view_func=None, *, minimum_role=FamilyMembership.Role.MEMBER):
    def decorator(func):
        @wraps(func)
        def wrapped(request, family_slug, pool_slug=None, *args, **kwargs):
            try:
                request.tenant_context = require_tenant_context(
                    request.user,
                    family=family_slug,
                    pool=pool_slug,
                    minimum_role=minimum_role,
                )
            except AuthenticationRequired:
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
            except TenantNotFound:
                raise Http404()
            except PermissionDeniedForTenant:
                return HttpResponseForbidden('Permission denied.')
            return func(request, family_slug, pool_slug, *args, **kwargs)
        return wrapped
```

```python
# pickem/pickem_api/authz.py:198-204
def get_user_family_memberships(user):
    _require_authenticated(user)
    return FamilyMembership.objects.filter(
        user=user,
        status=FamilyMembership.Status.ACTIVE,
        family__status=Family.Status.ACTIVE,
    ).select_related('family').order_by('family__name', 'family__slug')
```

## Recommended New Files

| File | Role | Data flow | Pattern source |
|---|---|---|---|
| `pickem/pickem_homepage/templates/pickem/onboarding.html` | template | request-response | Use `home.html` authenticated/anonymous branching lines 24-41 and Tailwind section/card classes from `home.html` lines 49-60. Keep focused: create, join, sign out/back. |
| `pickem/pickem_homepage/templates/pickem/create_family.html` | template | request-response + CRUD form | Use `base.html` content block lines 284-292 and existing form rendering conventions from forms widgets in `forms.py` lines 29-60. |
| `pickem/pickem_homepage/templates/pickem/join_family.html` | template | request-response + CRUD form | Same as create template; include manual invite-code field and validation error display. |
| `pickem/pickem_homepage/templates/pickem/family_picker.html` | template | request-response | Use `base.html` desktop/mobile dropdown styles lines 121-151 and 213-232 for action rows. |

Prefer adding helper functions inside existing modules for Phase 3 instead of new service modules unless the planner splits work further:

| Helper | Suggested location | Pattern source |
|---|---|---|
| `generate_unique_slug(model, value, scope=None)` | `pickem/pickem_homepage/views.py` or small utility if reused | Must satisfy model slug constraints from `models.py` lines 44-45 and 79-105. |
| `create_default_pool_for_family(family)` | `pickem/pickem_homepage/views.py` initially | Use `Pool` + `PoolSettings` model shape from `models.py` lines 73-184 and `get_season()` pattern from `views.py` lines 28-29. |
| `generate_invite_code()` / `hash_invite_code(raw_code)` | `pickem/pickem_homepage/views.py` initially | Store only `FamilyInvitation.code_hash`; see `models.py` lines 185-230 and tests lines 138-160. |
| `get_default_pool_for_family(family)` | `pickem/pickem_homepage/views.py` initially | Copy default-pool ordering semantics from `pickem_api/authz.py` lines 118-129, but filter by the requested family instead of legacy slug. |

## Recommended Existing Files to Touch

| File | Touch for | Concrete pattern |
|---|---|---|
| `pickem/pickem_homepage/forms.py` | Add `CreateFamilyForm` and `JoinFamilyForm`. | Use `forms.Form` validation style from `QuickCommentForm.clean_content()` lines 88-115. Use explicit widgets/attrs as in `MessageBoardPostForm` lines 29-60. |
| `pickem/pickem_homepage/views.py` | Add onboarding router, create, join, picker, tenant landing stub, invite create. | Use `@login_required`, POST validation, `messages`, `redirect`, and `render` from profile lines 702-791. Use JSON error shape only for AJAX endpoints, e.g. lines 1138-1204 and 1211-1317. |
| `pickem/pickem_homepage/urls.py` | Add readable Phase 3 routes. | Follow `path(..., views..., name=...)` style from lines 8-38. Add tenant URLs like `families/<slug:family_slug>/pools/<slug:pool_slug>/`. |
| `pickem/pickem_homepage/templates/pickem/base.html` | Add current family/pool indicator and switcher. | Insert near authenticated right-side nav lines 117-152 and mobile authenticated block lines 213-226. Reuse dropdown JS lines 342-438; no new framework. |
| `pickem/pickem_api/models.py` | No schema expected unless planner finds missing constraints. | Existing Phase 1 domain model already supports family, pool, membership, invitation, settings, audit lines 39-290. |
| `pickem/pickem_homepage/tests.py` | Add browser route, form, redirect, and denial tests. | Use `Client` route smoke tests lines 27-87 and `RequestFactory` decorator tests lines 131-207. |
| `pickem/pickem_api/tests.py` | Add invite lifecycle/hash helper tests if helper lands in API layer. | Use tenant domain tests lines 52-160 and authz tests lines 212-370. |

Recommended route names:

```python
# Pattern: pickem/pickem_homepage/urls.py:8-38
path('onboarding/', views.onboarding, name='onboarding')
path('families/create/', views.create_family, name='create_family')
path('families/join/', views.join_family, name='join_family')
path('families/', views.family_picker, name='family_picker')
path('families/<slug:family_slug>/pools/<slug:pool_slug>/', views.family_pool_home, name='family_pool_home')
path('families/<slug:family_slug>/pools/<slug:pool_slug>/invites/create/', views.create_family_invite, name='create_family_invite')
path('invites/<str:invite_code>/', views.accept_invite_link, name='accept_invite_link')
```

## Template/UI Patterns

Use the current Tailwind-in-template direction. Do not add Bootstrap-only UI for new onboarding screens.

Header/switcher insertion points:

```django
{# pickem/pickem_homepage/templates/pickem/base.html:117-152 #}
{% if user.is_authenticated %}
  <div class="relative dropdown-container">
    <button class="dropdown-trigger flex items-center space-x-2 px-3 py-2 rounded-xl border border-slate-600 hover:bg-slate-700 ..."
            aria-label="User menu" onclick="toggleDropdown(event, this)">
      ...
    </button>
    <div class="nav-dropdown absolute right-0 mt-2 w-64 bg-surface-light dark:bg-surface rounded-xl shadow-card ... hidden z-50 py-2">
      ...
    </div>
  </div>
{% endif %}
```

```django
{# pickem/pickem_homepage/templates/pickem/base.html:213-232 #}
{% if user.is_authenticated %}
  <div class="border-t border-border-light dark:border-border-subtle my-2"></div>
  <a class="block px-4 py-3 bg-primary text-white rounded-lg font-semibold text-center" href="/picks">
    <i class="fas fa-edit mr-2"></i>Submit Weekly Picks
  </a>
{% else %}
  <a class="block px-4 py-3 bg-primary text-white rounded-lg font-semibold text-center" href="{% provider_login_url 'google' %}">
    <i class="fab fa-google mr-2"></i>Sign In with Google
  </a>
{% endif %}
```

Dropdown/mobile behavior already exists:

```javascript
// pickem/pickem_homepage/templates/pickem/base.html:344-397
function toggleDropdown(event, button) { ... }
function toggleMobileDropdown(button) { ... }
```

Onboarding should replace signed-in global-home exposure for users with no active family. Copy the concise authenticated branching pattern from `home.html`:

```django
{# pickem/pickem_homepage/templates/pickem/home.html:24-41 #}
{% if user.is_authenticated %}
  ... Welcome back ...
{% else %}
  ... Sign in to start making picks ...
{% endif %}
```

## Test Patterns

Add focused tests before implementation.

Route behavior:

```python
# pickem/pickem_homepage/tests.py:27-87
class ViewSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(id=1, defaults={"domain": "testserver", "name": "testserver"})
        currentSeason.objects.create(season=2526, display_name="2025-2026")

    def setUp(self):
        self.client = Client()

    def test_profile_redirects_anon(self):
        resp = self.client.get("/profile/")
        self.assertEqual(resp.status_code, 302)
```

Authorization denial:

```python
# pickem/pickem_homepage/tests.py:177-207
def test_non_member_browser_request_raises_404(self):
    with self.assertRaises(Http404):
        self._view()(self._request(self.outsider), "smith-family", "main")

def test_member_browser_request_gets_403_for_admin_route(self):
    response = self._view(FamilyMembership.Role.ADMIN)(
        self._request(self.member), "smith-family", "main"
    )
    self.assertEqual(response.status_code, 403)
```

Model creation and uniqueness:

```python
# pickem/pickem_api/tests.py:58-94
family = Family.objects.create(name='Smith Family', slug='smith-family')
other_family = Family.objects.create(name='Jones Family', slug='jones-family')
Pool.objects.create(family=family, name='Main Pickem', slug='main', season=2526)
Pool.objects.create(family=other_family, name='Main Pickem', slug='main', season=2526)
with self.assertRaises(IntegrityError):
    Pool.objects.create(family=family, name='Duplicate Main', slug='main', season=2526)
```

Invitation hash storage:

```python
# pickem/pickem_api/tests.py:146-160
invitation = FamilyInvitation.objects.create(
    family=family,
    pool=pool,
    code_hash='sha256:invite-hash',
    role=FamilyMembership.Role.MEMBER,
    expires_at=timezone.now() + timedelta(days=7),
    max_uses=3,
    created_by=self.owner,
)
self.assertEqual(invitation.code_hash, 'sha256:invite-hash')
self.assertFalse(hasattr(invitation, 'code'))
self.assertFalse(hasattr(invitation, 'raw_code'))
```

Required Phase 3 tests:

| Test | File | Pattern |
|---|---|---|
| Anonymous `/` still public or redirects only where expected. | `pickem_homepage/tests.py` | `ViewSmokeTests` client assertions. |
| Signed-in zero-family user hits `/` and sees onboarding, not global league data. | `pickem_homepage/tests.py` | `Client.force_login`, assert template/content/status. |
| Signed-in one-family user hits `/` and redirects to `/families/<family>/pools/<pool>/`. | `pickem_homepage/tests.py` | Create `Family`, default `Pool`, active `FamilyMembership`. |
| Signed-in multi-family user hits `/` and gets picker or deterministic switcher route. | `pickem_homepage/tests.py` | Use `get_user_family_memberships()` ordering lines 198-204. |
| Create-family form rejects blank/duplicate names or slug collisions. | `pickem_homepage/tests.py` | Form validation pattern from `QuickCommentForm` lines 105-115. |
| Create-family POST creates `Family`, default current-season `Pool`, `PoolSettings`, owner membership. | `pickem_homepage/tests.py` or `pickem_api/tests.py` | Domain creation tests lines 58-136. |
| Owner invite creation stores hash only and response includes raw code once. | `pickem_homepage/tests.py` | Invite test lines 146-160 plus response content assertion. |
| Member cannot create owner-only invite. | `pickem_homepage/tests.py` | Decorator 403 test pattern lines 193-207. |
| Join accepts valid invite, creates/reactivates membership, increments use count, redirects to default pool. | `pickem_homepage/tests.py` | Use model fixtures + `Client.post`. |
| Join denies revoked, expired, exhausted, bad hash, and wrong family/pool states. | `pickem_homepage/tests.py` | Use `TenantAuthorizationHelperTest` negative style lines 280-328. |

## Patterns to Avoid

- Do not expose global standings/picks/home content to signed-in users with zero active family membership.
- Do not store raw invite codes in `FamilyInvitation`, admin, tests, sessions, or logs. Persist only `code_hash`; raw code is response-time only.
- Do not use legacy commissioner or superuser status as a tenant bypass. Phase 2 explicitly denies both without active membership (`pickem_api/tests.py` lines 299-304).
- Do not rely only on session state for tenant context. New Phase 3 tenant routes should carry `/families/<family_slug>/pools/<pool_slug>/...`.
- Do not use `allow_legacy_default=True` for new tenant onboarding routes. That fallback is explicit legacy compatibility only (`pickem_api/authz.py` lines 76-85, 110-133).
- Do not build full Phase 4 tenant-scoped gameplay pages or full Phase 5 invite management. Phase 3 should create entry points, default pool context, minimal invites, and switcher only.
- Do not add broad source refactors or a new frontend framework. Use existing Tailwind classes, Font Awesome icons, and current dropdown JavaScript.

## Plan Inputs

Files likely modified:

- `pickem/pickem_homepage/forms.py`
- `pickem/pickem_homepage/views.py`
- `pickem/pickem_homepage/urls.py`
- `pickem/pickem_homepage/templates/pickem/base.html`
- `pickem/pickem_homepage/tests.py`
- `pickem/pickem_api/tests.py` if invite hashing helpers are placed in API-level code

Files likely created:

- `pickem/pickem_homepage/templates/pickem/onboarding.html`
- `pickem/pickem_homepage/templates/pickem/create_family.html`
- `pickem/pickem_homepage/templates/pickem/join_family.html`
- `pickem/pickem_homepage/templates/pickem/family_picker.html`

Implementation notes for planner:

- Create-family should use `get_season()` and create `Pool(season=<current>, competition='nfl', is_default=True)` plus `PoolSettings`.
- Slugs should be deterministic from names with collision suffixing; family slug is globally unique, pool slug is unique within family.
- Invite code hashing needs a stable comparison format. Use one canonical prefix/algorithm string, e.g. `sha256:<hex>`, because existing tests use that shape.
- Invite acceptance must validate `code_hash`, active family, optional active pool belonging to family, not expired, not revoked, and `max_uses` not reached before membership creation.
- Existing inactive membership should be reactivated rather than creating a duplicate, because `FamilyMembership` has unique `(family, user)` (`models.py` lines 143-160).
- Root/post-login routing can live in `views.index` or a small helper it calls. Keep anonymous `/` behavior compatible with current public homepage.
- Header switcher context can be supplied by a context processor or by tenant-aware views. If added globally, use `get_user_family_memberships()` and catch unauthenticated users.

## PATTERNS COMPLETE

