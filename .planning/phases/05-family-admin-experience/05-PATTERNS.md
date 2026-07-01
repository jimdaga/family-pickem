# Phase 5: Family Admin Experience - Pattern Map

**Mapped:** 2026-07-01
**Files analyzed:** 9 likely new/modified files
**Analogs found:** 9 / 9
**Context inputs:** `05-CONTEXT.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, relevant code. No phase `RESEARCH.md` exists yet.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `pickem/pickem_homepage/urls.py` | route | request-response | `pickem/pickem_homepage/urls.py` tenant route block | exact |
| `pickem/pickem_homepage/views.py` admin hub | controller | request-response | `family_pool_home`, `create_family_invite`, tenant pick views | exact |
| `pickem/pickem_homepage/views.py` member/role actions | controller | CRUD | `accept_invitation_for_user`, create-family audit writes | role-match |
| `pickem/pickem_homepage/views.py` invite management | controller | CRUD | `create_family_invite`, invite acceptance helpers/tests | exact |
| `pickem/pickem_homepage/views.py` settings actions | controller | CRUD | `create_family`, `render_rules_page`, `PoolSettings` admin | role-match |
| `pickem/pickem_homepage/views.py` manual picks/week winner | controller | request-response + CRUD | tenant pick submit/edit plus legacy commissioner actions | partial |
| `pickem/pickem_homepage/forms.py` | form | transform | `CreateFamilyForm`, `JoinFamilyForm`, `PickSubmissionForm` | exact |
| `pickem/pickem_homepage/templates/pickem/family_admin*.html` | template/component | request-response | `family_pool_home.html`, `commissioners.html`, `rules.html` | role-match |
| `pickem/pickem_homepage/tests.py` | test | request-response + CRUD | tenant auth, invite, cross-family tests | exact |

## Pattern Assignments

### `pickem/pickem_homepage/urls.py` (route, request-response)

**Analog:** tenant route block in `pickem/pickem_homepage/urls.py`

**Route shape pattern** (lines 14-23):
```python
path(
    'families/<slug:family_slug>/pools/<slug:pool_slug>/',
    views.family_pool_home,
    name='family_pool_home',
),
path(
    'families/<slug:family_slug>/pools/<slug:pool_slug>/invites/create/',
    views.create_family_invite,
    name='create_family_invite',
),
```

**Apply to:** add admin routes under the same explicit tenant prefix, for example:
`family_pool_admin`, `family_pool_admin_members`, `family_pool_admin_invites`, `family_pool_admin_settings`, `family_pool_admin_audit`, `family_pool_admin_manual_pick`, `family_pool_admin_week_winner`.

**Legacy commissioner route risk** (lines 111-117):
```python
path('commissioners/', views.commissioners, name='commissioners'),
path('commissioners/set-week-winner/', views.set_week_winner, name='set_week_winner'),
path('commissioners/submit-manual-pick/', views.submit_manual_pick, name='submit_manual_pick'),
path('commissioners/get-user-picks/', views.get_user_picks, name='get_user_picks'),
```

**Planner note:** Phase 5 should replace or deny these global routes after tenant replacements exist. Do not leave these paths mutating global data.

### `pickem/pickem_homepage/views.py` Admin Hub (controller, request-response)

**Analog:** `family_pool_home`

**Auth/import pattern** (lines 41-43):
```python
from pickem_api.authz import get_user_family_memberships
from pickem_api.models import Family, FamilyAuditLog, FamilyInvitation, FamilyMembership, Pool, PoolSettings
from pickem_homepage.authz import family_member_required
```

**Tenant context and scoped query pattern** (lines 508-608):
```python
@family_member_required
def family_pool_home(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    family = tenant_context.family
    pool = tenant_context.pool
    gameseason = pool.season or get_season()

    standings_qs = (
        userSeasonPoints.objects.filter(pool=pool, gameseason=gameseason)
        .order_by('-total_points', 'userID')
    )
    active_members = (
        FamilyMembership.objects.filter(
            family=family,
            status=FamilyMembership.Status.ACTIVE,
            user__is_active=True,
        )
        .select_related('user')
        .order_by('user__username')[:10]
    )
```

**Apply to:** admin hub views should start from `request.tenant_context`, then query `FamilyMembership`, `FamilyInvitation`, `PoolSettings`, `FamilyAuditLog`, `GamePicks`, and `userSeasonPoints` through `tenant_context.family` or `tenant_context.pool`.

**Role guard pattern:** use `@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)` for admin hub pages. Use `OWNER` for ownership-sensitive POSTs.

### `pickem/pickem_homepage/views.py` Member And Role Actions (controller, CRUD)

**Analog:** `accept_invitation_for_user` and create-family audit writes

**Transactional membership update pattern** (lines 244-270):
```python
with transaction.atomic():
    invitation = get_valid_invitation_for_code(raw_code)
    if not invitation:
        return None, None, None

    membership, created = FamilyMembership.objects.select_for_update().get_or_create(
        family=invitation.family,
        user=request.user,
        defaults={
            'role': invitation.role,
            'status': FamilyMembership.Status.ACTIVE,
        },
    )
    previous_role = membership.role
    previous_status = membership.status
    if not created:
        membership.role = invitation.role
        membership.status = FamilyMembership.Status.ACTIVE
        membership.save(update_fields=['role', 'status', 'updated_at'])
```

**Audit metadata pattern** (lines 272-290):
```python
FamilyAuditLog.objects.create(
    family=invitation.family,
    pool=pool,
    actor=request.user,
    action=(
        FamilyAuditLog.Action.MEMBERSHIP_CREATED
        if created else FamilyAuditLog.Action.MEMBERSHIP_UPDATED
    ),
    target_type='FamilyMembership',
    target_id=str(membership.id),
    metadata={
        'source': 'invite_acceptance',
        'invitation_id': invitation.id,
        'role': membership.role,
        'previous_role': previous_role,
        'previous_status': previous_status,
        'status': membership.status,
    },
```

**Apply to:** role/status changes. Lock target membership with `select_for_update()`, store previous/new role and status, and create `MEMBERSHIP_UPDATED` audit entries. Add explicit owner checks for promote/demote admin, transfer owner, deactivate/reactivate, and last-active-owner protection.

### `pickem/pickem_homepage/views.py` Invite Management (controller, CRUD)

**Analog:** invite helpers and `create_family_invite`

**Hash-only invite helpers** (lines 109-124):
```python
def normalize_invite_code(raw_code):
    return ''.join(
        char.lower()
        for char in (raw_code or '').strip()
        if char.isalnum()
    )

def hash_invite_code(raw_code):
    normalized_code = normalize_invite_code(raw_code)
    digest = hashlib.sha256(normalized_code.encode('utf-8')).hexdigest()
    return f"sha256:{digest}"

def generate_invite_code():
    return secrets.token_urlsafe(24)
```

**One-time raw code display pattern** (lines 450-489):
```python
@require_http_methods(["POST"])
@family_member_required(minimum_role=FamilyMembership.Role.OWNER)
def create_family_invite(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    raw_code = generate_invite_code()

    with transaction.atomic():
        invitation = FamilyInvitation.objects.create(
            family=tenant_context.family,
            pool=tenant_context.pool,
            code_hash=hash_invite_code(raw_code),
            role=FamilyMembership.Role.MEMBER,
            expires_at=timezone.now() + timedelta(days=14),
            max_uses=20,
            created_by=request.user,
        )
```

**Invite audit pattern** (lines 466-478):
```python
FamilyAuditLog.objects.create(
    family=tenant_context.family,
    pool=tenant_context.pool,
    actor=request.user,
    action=FamilyAuditLog.Action.INVITATION_CREATED,
    target_type='FamilyInvitation',
    target_id=str(invitation.id),
    metadata={
        'role': invitation.role,
        'expires_at': invitation.expires_at.isoformat(),
        'max_uses': invitation.max_uses,
    },
    **get_invite_audit_context(request),
)
```

**Apply to:** invite create/list/revoke. Listing should show safe metadata only: role, expiry, max uses, use count, creator, revoked state, created date. Never expose `code_hash` or raw code in list/audit views. Revocation should set `is_revoked=True`, use `INVITATION_REVOKED`, and log no raw code.

### `pickem/pickem_homepage/views.py` Family/Pool/Rules Settings (controller, CRUD)

**Analog:** `create_family`, `render_rules_page`, `PoolSettings` model

**Server-derived family/pool creation and audit pattern** (lines 320-377):
```python
family = Family.objects.create(
    name=form.cleaned_data['name'],
    slug=generate_unique_slug(Family, form.cleaned_data['name']),
    status=Family.Status.ACTIVE,
)
pool = Pool.objects.create(
    family=family,
    name='Main Pickem',
    slug=generate_unique_slug(
        Pool,
        'Main Pickem',
        scoped_filters={'family': family},
    ),
    season=get_season(),
    competition='nfl',
    status=Pool.Status.ACTIVE,
    is_default=True,
)
PoolSettings.objects.create(pool=pool)
```

**Pool settings model surface** (`pickem/pickem_api/models.py` lines 164-183):
```python
class PoolSettings(models.Model):
    pool = models.OneToOneField(Pool, on_delete=models.PROTECT, related_name='settings')
    picks_lock_at_kickoff = models.BooleanField(default=True)
    allow_tiebreaker = models.BooleanField(default=True)
```

**Rules display context pattern** (`pickem/pickem_homepage/templates/pickem/rules.html` lines 23-35):
```django
{% if family and pool %}
<div class="flex flex-col items-end gap-1.5">
    <span class="text-sm font-semibold text-text-dark dark:text-white">{{ family.name }} — {{ pool.name }}</span>
    {% if pool_settings %}
    <div class="flex gap-2">
        <span class="px-2 py-0.5 text-xs bg-surface-light dark:bg-slate-700 rounded border border-border-light dark:border-slate-600 text-text-secondary-light dark:text-text-secondary">
            Locking: <span class="font-semibold text-text-dark dark:text-white">{% if pool_settings.picks_lock_at_kickoff %}On{% else %}Off{% endif %}</span>
        </span>
```

**Apply to:** settings edit forms should mutate only `tenant_context.family`, `tenant_context.pool`, and `tenant_context.pool.settings`. Use `POOL_SETTINGS_UPDATED` audit action for represented rules/settings; use `MEMBERSHIP_UPDATED` for role/status; extend `FamilyAuditLog.Action` only if a family-name-only update cannot be represented safely in metadata.

### `pickem/pickem_homepage/views.py` Manual Pick Admin (controller, CRUD)

**Safe analog:** tenant pick submit/edit, not legacy commissioner write

**Server-derived pick save pattern** (lines 1331-1379):
```python
form = PickSubmissionForm(request.POST)
if not form.is_valid():
    return JsonResponse({'error': True, 'message': 'Invalid pick'}, status=400)

game = GamesAndScores.objects.filter(
    id=form.cleaned_data['game_id'],
    gameseason=tenant_context.pool.season,
    gameWeek=str(game_week),
    competition=tenant_context.pool.competition,
).first()
if not game:
    return JsonResponse({'error': True, 'message': 'Invalid pick'}, status=400)

selected_pick = form.cleaned_data['pick']
if selected_pick not in [game.awayTeamSlug, game.homeTeamSlug]:
    return JsonResponse({'error': True, 'message': 'Invalid pick'}, status=400)
```

**Unsafe legacy behavior to migrate carefully** (lines 2486-2536):
```python
@commissioner_required
@require_http_methods(["POST"])
@csrf_exempt
def submit_manual_pick(request):
    data = json.loads(request.body)
    user_id = data.get('user_id')
    game_id = data.get('game_id')
    pick = data.get('pick')
    ...
    user = User.objects.get(id=user_id)
    game = GamesAndScores.objects.get(id=game_id)
    pick_id = f"{user.id}-{game.id}"
    pick_obj, created = GamePicks.objects.update_or_create(
        id=pick_id,
        defaults={
            'userEmail': user.email,
            'uid': user.id,
```

**Apply to:** use the legacy manual-pick UI/business intent, but replace the implementation with tenant scoping:
- Guard with `@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)`.
- Validate target user has active membership in `tenant_context.family`.
- Validate game belongs to `tenant_context.pool.season` and `tenant_context.pool.competition`.
- Use tenant pick ID format from tests: `f"{pool.id}-{user.id}-{game.id}"`.
- Store `pool=tenant_context.pool`.
- Add `FamilyAuditLog.Action.MANUAL_PICK_UPDATED` with actor, target user, game id, previous pick, new pick, and request context.
- Do not copy `@csrf_exempt` into new endpoints.

### `pickem/pickem_homepage/views.py` Week Winner Admin (controller, CRUD)

**Business analog:** legacy `set_week_winner` and `get_week_candidates`

**Legacy winner logic to scope and harden** (lines 2319-2376):
```python
data = json.loads(request.body)
week_number = data.get('week_number')
winner_uid = data.get('winner_uid')
gameseason = data.get('gameseason')

winner_field = f"week_{week_number}_winner"
userSeasonPoints.objects.filter(gameseason=gameseason).update(**{winner_field: False})

winner_record = userSeasonPoints.objects.filter(
    userEmail=User.objects.get(id=winner_uid).email,
    gameseason=gameseason
).first()
```

**Candidate query to scope** (lines 2439-2483):
```python
week_picks = GamePicks.objects.filter(
    gameseason=gameseason,
    gameWeek=week,
    competition=competition,
    pick_correct=True
)
user_points = week_picks.values('uid').annotate(
    wins=Count('uid')
).order_by('-wins')
```

**Apply to:** require `1 <= int(week_number) <= 18` before building dynamic field names. Filter `GamePicks` and `userSeasonPoints` by `pool=tenant_context.pool`. Validate `winner_uid` belongs to an active family membership and has a `userSeasonPoints` row in the current pool/season. Add `WEEK_WINNER_UPDATED` audit. This is a security-sensitive replacement, not a copy of the old global function.

### `pickem/pickem_homepage/forms.py` (form, transform)

**Analog:** `CreateFamilyForm`, `JoinFamilyForm`, `PickSubmissionForm`

**Tailwind form widget pattern** (lines 7-24):
```python
class CreateFamilyForm(forms.Form):
    name = forms.CharField(
        label="Family name",
        max_length=200,
        min_length=2,
        strip=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full rounded-lg border border-border-light dark:border-border-subtle bg-white dark:bg-surface px-4 py-3 text-slate-900 dark:text-text-primary placeholder-slate-500 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20',
            'placeholder': 'Smith Family',
            'autocomplete': 'organization',
        }),
    )
```

**Input-only admin mutation pattern** (lines 68-72):
```python
class PickSubmissionForm(forms.Form):
    game_id = forms.IntegerField(required=True)
    pick = forms.CharField(max_length=250, required=True, strip=True)
    tieBreakerScore = forms.IntegerField(required=False, min_value=0, max_value=200)
    tieBreakerYards = forms.IntegerField(required=False, min_value=0, max_value=2000)
```

**Do not copy:** `GamePicksForm` lines 46-65 exposes user, season, game metadata, and correctness. New admin forms should accept only action inputs; family, pool, actor, target object, and derived fields must come from server-side lookups.

### `pickem/pickem_homepage/templates/pickem/family_admin*.html` (template/component, request-response)

**Analog:** `family_pool_home.html`, `commissioners.html`, `rules.html`

**Tenant page header and context chips** (`family_pool_home.html` lines 6-25):
```django
<main class="max-w-6xl mx-auto px-6 py-10">
    <section class="mb-8">
        <p class="text-sm font-semibold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary mb-3">Current pool</p>
        <h1 class="text-3xl lg:text-4xl font-black text-text-dark dark:text-white mb-4">
            {{ family.name }}
        </h1>
        <div class="flex flex-wrap items-center gap-3 text-sm text-text-secondary-light dark:text-text-secondary">
            <span class="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-surface-light dark:bg-surface border border-border-light dark:border-border-subtle">
                <i class="fas fa-trophy text-primary"></i>
                {{ pool.name }}
            </span>
```

**Operational table/card pattern** (`commissioners.html` lines 77-123):
```django
<div class="overflow-x-auto rounded-xl shadow-md">
    <table class="w-full">
        <thead>
            <tr class="bg-primary text-white">
                <th class="px-4 py-3 text-left font-semibold">Player</th>
                <th class="px-4 py-3 text-left font-semibold">Correct Picks</th>
                <th class="px-4 py-3 text-left font-semibold">Tiebreaker</th>
                <th class="px-4 py-3 text-left font-semibold">Action</th>
            </tr>
        </thead>
        <tbody class="bg-white dark:bg-surface divide-y divide-border-light dark:divide-border-subtle">
```

**Invite one-time code display** (`family_pool_home.html` lines 155-166):
```django
{% if invite_code %}
<section class="mt-6 bg-surface-light dark:bg-surface border border-primary/30 rounded-lg p-5">
    <p class="text-sm font-semibold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary mb-2">Invite created</p>
    <h2 class="text-lg font-bold text-text-dark dark:text-white mb-2">Copy this code now</h2>
    <p class="text-sm text-text-secondary-light dark:text-text-secondary mb-4">
        The raw invite code is shown only once.
    </p>
```

**Apply to:** admin hub should be utilitarian: header, compact context chips, tab/section navigation, tables/forms, empty states. Keep server-side auth as source of truth; hiding controls is only a UX affordance.

### `pickem/pickem_homepage/tests.py` (test, request-response + CRUD)

**Analog:** auth decorator tests, invite tests, tenant isolation tests

**Auth denial split pattern** (lines 2620-2691):
```python
def test_anonymous_browser_request_redirects_to_login(self):
    response = self._view()(self._request(AnonymousUser()), "smith-family", "main")
    self.assertEqual(response.status_code, 302)
    self.assertIn("/accounts/login/", response["Location"])

def test_non_member_browser_request_raises_404(self):
    with self.assertRaises(Http404):
        self._view()(self._request(self.outsider), "smith-family", "main")

def test_member_browser_request_gets_403_for_admin_route(self):
    response = self._view(FamilyMembership.Role.ADMIN)(
        self._request(self.member), "smith-family", "main"
    )
    self.assertEqual(response.status_code, 403)
```

**Invite hash/audit tests** (lines 2332-2374):
```python
response = self.client.post(self._create_invite_url())

invitation = FamilyInvitation.objects.get(family=self.family)
raw_code = response.context["invite_code"]

self.assertTrue(invitation.code_hash.startswith("sha256:"))
self.assertNotEqual(invitation.code_hash, raw_code)
self.assertFalse(
    FamilyInvitation.objects.filter(code_hash__icontains=raw_code).exists()
)
self.assertNotIn(raw_code, str(audit.metadata))
```

**Cross-pool fixture pattern** (lines 1567-1580):
```python
def _active_membership(self, user, family, role=FamilyMembership.Role.MEMBER):
    return FamilyMembership.objects.create(
        family=family,
        user=user,
        role=role,
        status=FamilyMembership.Status.ACTIVE,
    )

def _tenant_url(self, route_name, family=None, pool=None, **kwargs):
    family = family or self.smith_family
    pool = pool or self.smith_pool
    route_kwargs = {"family_slug": family.slug, "pool_slug": pool.slug}
```

**Apply to:** tests must cover anonymous redirect, outsider 404, active member 403 for admin routes, inactive membership denial, admin/owner success, owner-only sensitive actions, cross-family object IDs in body/query, forged family/pool ids, invalid week numbers, CSRF failures for POSTs, raw invite code non-disclosure, audit log scoping.

## Shared Patterns

### Tenant Authorization

**Source:** `pickem/pickem_homepage/authz.py` lines 16-34
```python
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
```

**Apply to:** every Phase 5 family admin route.

### Role Ordering

**Source:** `pickem/pickem_api/authz.py` lines 11-15 and 45-49
```python
ROLE_ORDER = {
    FamilyMembership.Role.MEMBER: 10,
    FamilyMembership.Role.ADMIN: 20,
    FamilyMembership.Role.OWNER: 30,
}

def role_allows(actual_role, minimum_role):
    try:
        return ROLE_ORDER[actual_role] >= ROLE_ORDER[minimum_role]
    except KeyError:
        return False
```

**Apply to:** least-privilege checks. Do not use `UserProfile.is_commissioner` or `is_superuser` as tenant bypass.

### Tenant Context Resolution

**Source:** `pickem/pickem_api/authz.py` lines 175-195
```python
def require_tenant_context(
    user,
    *,
    family: FamilyRef,
    pool: Optional[PoolRef] = None,
    minimum_role=FamilyMembership.Role.MEMBER,
) -> TenantContext:
    resolved_family = resolve_family(family)
    resolved_pool = None
    if pool is not None:
        resolved_pool = resolve_pool_context(pool=pool, family=resolved_family)
    membership = require_family_membership(
        user,
        resolved_family,
        minimum_role=minimum_role,
    )
    return TenantContext(
        family=resolved_family,
        pool=resolved_pool,
        membership=membership,
    )
```

**Apply to:** all routes should trust `request.tenant_context`, not POSTed `family_id` or `pool_id`.

### Audit Actions

**Source:** `pickem/pickem_api/models.py` lines 234-243
```python
class FamilyAuditLog(models.Model):
    class Action(models.TextChoices):
        INVITATION_CREATED = 'invitation_created', 'Invitation created'
        INVITATION_REVOKED = 'invitation_revoked', 'Invitation revoked'
        MEMBERSHIP_CREATED = 'membership_created', 'Membership created'
        MEMBERSHIP_UPDATED = 'membership_updated', 'Membership updated'
        POOL_SETTINGS_UPDATED = 'pool_settings_updated', 'Pool settings updated'
        MANUAL_PICK_UPDATED = 'manual_pick_updated', 'Manual pick updated'
        WEEK_WINNER_UPDATED = 'week_winner_updated', 'Week winner updated'
```

**Apply to:** Phase 5 can likely use existing action choices. If extending actions, coordinate with current dirty `pickem_api/models.py` and migration work.

### Admin Visibility In Header

**Source:** `base.html` current commissioner nav lines 101-105 and mobile lines 242-245
```django
{% if user_is_commissioner %}
<a class="nav-link-base" href="{% url 'commissioners' %}" aria-label="Commissioners Dashboard">
    <i class="fas fa-crown"></i>
</a>
{% endif %}
```

**Apply to:** replace this UX affordance with tenant-role-aware admin link only when `current_family`, `current_pool`, and `current_membership.role in ('owner', 'admin')`. Server-side `family_member_required` remains mandatory.

## Dirty Worktree Risk Notes

| File | Current dirty status | Phase 5 risk | Planner guidance |
|---|---|---|---|
| `pickem/pickem_homepage/templates/pickem/base.html` | modified | Admin navigation link must merge with active frontend/logo refactor | Make minimal targeted insert; inspect current file before editing. |
| `pickem/pickem_homepage/templates/pickem/commissioners.html` | modified | Legacy commissioner disable/replacement overlaps UI refactor | Prefer denying legacy view in Python and avoid broad template rewrite unless route still renders. |
| `pickem/pickem_homepage/templates/pickem/family_pool_home.html` | modified | Existing invite button/one-time display may move | Reuse current pattern but re-read before patching. |
| `pickem/pickem_homepage/templates/pickem/rules.html` | modified | Settings display/edit may overlap active Tailwind refactor | Add admin settings in new admin template where possible; avoid broad rules-page churn. |
| `pickem/pickem_homepage/static/css/input.css`, `tailwind.css`, `tailwind.config.js` | modified | Styling changes could overwrite frontend work | Avoid CSS changes unless a class is missing; prefer existing utility classes. |
| `pickem/pickem_api/models.py`, `admin.py`, `0076_add_family_logo_url.py` | modified/untracked migration | Audit action or family field changes can conflict | Avoid model changes if existing audit choices suffice; if unavoidable, inspect and preserve logo/schema changes. |
| Screenshots and `.playwright-mcp/` | untracked | Not relevant to planning | Do not stage or modify. |

## No Analog Found

None. Every likely Phase 5 file has a usable in-repo analog, but manual pick/week-winner logic has only partial safe analogs because legacy commissioner code is global and has CSRF/dynamic-field risks.

## Metadata

**Analog search scope:** `pickem/pickem_homepage`, `pickem/pickem_api`, `pickem/pickem`, `.planning/codebase`
**Strong analog files read:** `authz.py`, `views.py`, `urls.py`, `forms.py`, `models.py`, `admin.py`, `context_processors.py`, `base.html`, `family_pool_home.html`, `commissioners.html`, `rules.html`, `tests.py`
**Pattern extraction date:** 2026-07-01
