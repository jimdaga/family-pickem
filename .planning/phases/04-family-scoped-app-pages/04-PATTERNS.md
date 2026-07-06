# Phase 04: Family-Scoped App Pages - Pattern Map

**Mapped:** 2026-06-29
**Files analyzed:** 12 likely new/modified files
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pickem/pickem_homepage/urls.py` | route | request-response | `pickem/pickem_homepage/urls.py` lines 14-24 | exact |
| `pickem/pickem_homepage/views.py` | controller | request-response + CRUD | `pickem/pickem_homepage/views.py` lines 448-457, 704-851, 940-1090, 1208-1547, 1623-1895 | exact/role-match |
| `pickem/pickem_homepage/authz.py` | middleware/decorator | request-response | `pickem/pickem_homepage/authz.py` lines 16-40 | exact |
| `pickem/pickem/context_processors.py` | provider | request-response | `pickem/pickem/context_processors.py` lines 97-146 | exact |
| `pickem/pickem_homepage/templates/pickem/base.html` | component/template | request-response | `pickem/pickem_homepage/templates/pickem/base.html` lines 117-167, 263-299 | exact |
| `pickem/pickem_homepage/templates/pickem/family_pool_home.html` | component/template | request-response | `pickem/pickem_homepage/templates/pickem/family_pool_home.html` lines 1-80 | exact |
| `pickem/pickem_homepage/templates/pickem/home.html` | component/template | request-response + AJAX | `pickem/pickem_homepage/templates/pickem/home.html` lines 360-430, 546-620, 850-1145 | role-match |
| `pickem/pickem_homepage/templates/pickem/picks.html` | component/template | request-response + CRUD | `pickem/pickem_homepage/templates/pickem/picks.html` lines 27-80, 578-586 | role-match |
| `pickem/pickem_homepage/templates/pickem/scores.html` | component/template | request-response | `pickem/pickem_homepage/templates/pickem/scores.html` lines 90-180, 550-690 | role-match |
| `pickem/pickem_homepage/templates/pickem/standings.html` | component/template | request-response | `pickem/pickem_homepage/templates/pickem/standings.html` lines 83-150 | role-match |
| `pickem/pickem_homepage/templates/pickem/rules.html` | component/template | request-response | `pickem/pickem_homepage/templates/pickem/rules.html` lines 11-80 | role-match |
| `pickem/pickem_homepage/tests.py` | test | request-response + CRUD + AJAX | `pickem/pickem_homepage/tests.py` lines 100-224, 513-839, 883-959, 1119-1323 | exact |

## Pattern Assignments

### `pickem/pickem_homepage/urls.py` (route, request-response)

**Analog:** `pickem/pickem_homepage/urls.py`

**Tenant route pattern** (lines 14-24):
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
path('invites/<str:invite_code>/', views.accept_invite_link, name='accept_invite_link'),
```

**Apply to Phase 4:** add tenant route variants under `families/<slug:family_slug>/pools/<slug:pool_slug>/` for dashboard/home, picks, pick edit, scores current week, scores by week, standings, rules, user profiles/players, and message-board AJAX. Keep readable route names, for example `family_pool_scores`, `family_pool_scores_week`, `family_pool_picks`, `family_pool_standings`, `family_pool_rules`, `family_pool_user_profile`, `family_pool_create_post`.

**Legacy bridge pattern** (lines 25-44):
```python
path('scores/', views.scores, name='scores'),
path('standings/', views.standings, name='standings'),
path('rules/', views.rules, name='rules'),
path('picks/', views.submit_game_picks, name='game_picks'),
path('picks/edit/', views.edit_game_pick, name='edit_game_pick'),
path('user/<int:user_id>/', views.user_profile, name='user_profile'),
path('message-board/create-post/', views.create_post, name='create_post'),
```

**Apply to Phase 4:** do not keep these signed-in private routes rendering global data. Convert each legacy view to redirect authenticated users through `get_family_pool_choices()` when one/default tenant exists, and keep anonymous/public behavior only where Phase 4 explicitly allows it.

---

### `pickem/pickem_homepage/views.py` (controller, tenant request-response)

**Analog:** `family_pool_home`

**Guarded tenant page pattern** (lines 448-457):
```python
@family_member_required
def family_pool_home(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    context = {
        'family': tenant_context.family,
        'pool': tenant_context.pool,
        'membership': tenant_context.membership,
        'gameseason': get_season(),
    }
    return render(request, 'pickem/family_pool_home.html', context)
```

**Apply to Phase 4:** every tenant gameplay/community page should start from `request.tenant_context`. Use `tenant_context.pool` for picks, standings, weekly winners, stats, and score overlays. Use `tenant_context.family` for message board, profiles/player lists, and display-only family context.

**Default tenant redirect pattern** (lines 461-468):
```python
if request.user.is_authenticated:
    family_choices = get_family_pool_choices(request.user)
    if not family_choices:
        return redirect('onboarding')
    if len(family_choices) == 1 and family_choices[0]['url']:
        return redirect(family_choices[0]['url'])
    return redirect('family_picker')
```

**Apply to Phase 4:** extract a small compatibility helper if useful, but preserve this behavior: signed-in legacy private routes redirect to tenant context or picker/onboarding before querying private global data.

---

### Dashboard/Home Tenant View (controller/template, request-response)

**Analog:** legacy `index()` plus tenant shell.

**Existing global dashboard queries to scope or remove** (lines 484-608):
```python
season_winner = userSeasonPoints.objects.filter(year_winner=True, gameseason=gameseason).first()
top_players = userSeasonPoints.objects.filter(gameseason=gameseason).order_by('-total_points')[:5]
...
total_picks = GamePicks.objects.filter(gameseason=gameseason, slug__in=finished_game_slugs).count()
...
message_posts = MessageBoardPost.objects.filter(is_active=True).order_by('-is_pinned', '-created_at')[:13]
```

**Safe tenant rewrite:** add `pool=tenant_context.pool` to `userSeasonPoints` and `GamePicks`; add `family=tenant_context.family` to `MessageBoardPost`, `MessageBoardVote`, comments, and post badges. If a widget cannot be safely scoped, omit it from the tenant dashboard instead of showing global data.

**Template card/link pattern to rewrite** (home template lines 360-400):
```django
{% if user.is_authenticated %}
<a href="/picks/" class="group relative block p-5 ...">
...
<a href="/scores/" class="group relative block p-5 ...">
...
<a href="/standings/" class="group relative block p-5 ...">
...
<a href="/rules/" class="group relative block p-5 ...">
```

**Apply to Phase 4:** use named tenant URLs with `family.slug` and `pool.slug`; avoid hardcoded `/picks/`, `/scores/`, `/standings/`, `/rules/` inside tenant pages.

---

### Picks And Pick Edit (controller/template, CRUD + request-response)

**Analog:** `submit_game_picks()` and `edit_game_pick()`.

**Current read pattern needing pool filter** (lines 957-968):
```python
game_list = GamesAndScores.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition).distinct()
...
picks = GamePicks.objects.filter(
    gameseason=gameseason,
    gameWeek=game_week,
    competition=game_competition,
    userEmail=request.user.email,
)
```

**Current unsafe write pattern to replace** (lines 994-998):
```python
if request.method == 'POST':
   form = GamePicksForm(request.POST)
   if form.is_valid():
       form.save()
       return render(request, 'pickem/picks.html', context)
```

**Current edit pattern needing pool guard** (lines 1023-1033):
```python
existing_pick = GamePicks.objects.get(id=pick_id, userEmail=request.user.email)
...
game = GamesAndScores.objects.get(id=existing_pick.pick_game_id)
```

**Safe tenant rewrite:** keep `GamesAndScores`, `GameWeeks`, and `Teams` global; build picks server-side with `pool=tenant_context.pool`, `uid=request.user.id`, `userID=str(request.user.id)`, `userEmail=request.user.email`, and game fields from the selected `GamesAndScores` row. Validate `game_id` belongs to the server-selected season/week/competition and validate `pick` is one of the game team slugs. For edit, fetch `GamePicks.objects.get(id=pick_id, pool=tenant_context.pool, userEmail=request.user.email)` or by `(pool, userID, pick_game_id)` if the ID format changes.

**Form warning:** `GamePicksForm` currently exposes server-owned fields (forms.py lines 46-65). Phase 4 should avoid trusting that form for tenant POSTs, or reduce it to only user-selectable values.

---

### Scores And Week Scores (controller/template, request-response)

**Analog:** `scores()` / `scores_long()`.

**Current score facts can stay global** (lines 765-792):
```python
game_list = GamesAndScores.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)
...
wins_losses = Teams.objects.filter(gameseason=gameseason)
```

**Current private overlays need pool filter** (lines 770-795):
```python
picks = GamePicks.objects.filter(gameseason=gameseason, gameWeek=game_week, competition=game_competition)
...
user_points = points.filter(gameseason=gameseason).values('uid').annotate(wins=Coalesce(Count('uid'), 0)).order_by('-wins', '-uid')
...
week_winner = userSeasonPoints.objects.filter(**{winner_object: True},gameseason=gameseason).distinct()
```

**Template overlay to protect** (scores template lines 555-610):
```django
{% for pick in picks %}
    {% if pick.pick == game.awayTeamSlug %}
        <a href="{% url 'user_profile' pick.uid %}" class="group">
...
{% if not picks %}
    <span class="no-picks-message">No picks available</span>
{% endif %}
```

**Safe tenant rewrite:** add `pool=tenant_context.pool` to all pick, point, player, winner, user weekly stats, and pick avatar/name overlays. Profile links from score overlays should go to the tenant profile route, not global `user_profile`.

---

### Standings (controller/template, request-response)

**Analog:** `standings()`.

**Current global pattern to scope** (lines 704-739):
```python
selected_season = str(request.GET.get('season', get_season()))
player_points = userSeasonPoints.objects.filter(gameseason=selected_season).order_by('-total_points')
season_winner = userSeasonPoints.objects.filter(year_winner=True, gameseason=selected_season).first()
players = User.objects.filter(is_active=True)
```

**Template player link pattern** (standings template lines 117-130):
```django
<a href="?season={{ season.value }}"
...
<a href="{% url 'user_profile' player.userID %}"
```

**Safe tenant rewrite:** filter `userSeasonPoints` by `pool=tenant_context.pool`; restrict `players` to active users with `FamilyMembership` in `tenant_context.family`; preserve `?season=` query selection on the tenant standings route. Rewrite profile links to the tenant profile route.

---

### Rules (controller/template, request-response)

**Analog:** current static `rules()`.

**Current view pattern** (lines 1093-1099):
```python
def rules(request):
    gameseason = get_season()
    template = loader.get_template('pickem/rules.html')
    context = {
        'gameseason': gameseason,
    }
    return HttpResponse(template.render(context, request))
```

**Pool settings model source** (`pickem/pickem_api/models.py` lines 163-173):
```python
class PoolSettings(models.Model):
    pool = models.OneToOneField(Pool, on_delete=models.PROTECT, related_name='settings')
    picks_lock_at_kickoff = models.BooleanField(default=True)
    allow_tiebreaker = models.BooleanField(default=True)
```

**Safe tenant rewrite:** make tenant `rules` guarded and pass `tenant_context.family`, `tenant_context.pool`, and `pool.settings` when present. Keep static rules as fallback copy; do not add editing forms in Phase 4.

---

### Profiles And Players (controller/template, request-response)

**Analog:** `user_profile()`.

**Current global/private profile checks** (lines 1208-1229):
```python
profile_user = get_object_or_404(User, id=user_id)
...
if user_profile.private_profile and request.user != profile_user:
    return render(request, 'pickem/user_profile_private.html', {...})
season_points = userSeasonPoints.objects.filter(userID=str(user_id), gameseason=gameseason).first()
```

**Current global stats/picks/posts queries to scope** (lines 1317-1529):
```python
user_picks = GamePicks.objects.filter(userID=str(user_id), gameseason=gameseason)
...
recent_picks = GamePicks.objects.filter(
    userID=str(user_id),
    gameseason=gameseason
).select_related().order_by('-gameWeek')[:5]
posts_count = MessageBoardPost.objects.filter(user_id=user_id).count()
```

**Safe tenant rewrite:** before loading stats, require active membership for both `request.user` and `profile_user` in `tenant_context.family`; return 404 for non-members. Scope points and picks by `pool=tenant_context.pool`; scope posts by `family=tenant_context.family`. Keep the profile privacy check, but do not let it substitute for tenant membership.

---

### Message Board And AJAX (controller/template, AJAX + CRUD)

**Analog:** existing AJAX views plus family-scoped message models.

**Family fields available** (`pickem/pickem_homepage/models.py` lines 100-125, 148-173, 203-226):
```python
family = models.ForeignKey("pickem_api.Family", on_delete=models.SET_NULL, related_name='message_board_posts', blank=True, null=True)
...
models.Index(fields=['family', 'is_active', 'created_at'], name='post_family_active_idx')
```

**Current create-post pattern needing family assignment** (lines 1623-1665):
```python
@login_required
@require_http_methods(["POST"])
def create_post(request):
    content = request.POST.get('content', '').strip()
    ...
    post = MessageBoardPost.objects.create(
        user=request.user,
        title=title,
        content=content
    )
    return JsonResponse({'success': True, 'post_id': post.id, ...})
```

**Current IDOR-prone lookup pattern to replace** (lines 1685-1698, 1748-1769, 1811-1832, 1862-1889):
```python
post = get_object_or_404(MessageBoardPost, id=post_id, is_active=True)
parent = get_object_or_404(MessageBoardComment, id=parent_id, is_active=True)
...
existing_vote = MessageBoardVote.objects.filter(user=request.user, post=post).first()
...
post = get_object_or_404(MessageBoardPost, id=post_id, is_active=True)
comments = post.get_top_level_comments()
```

**Template JS endpoints to rewrite** (home template lines 861-887, 1010-1138):
```javascript
fetch('/message-board/create-post/', { method: 'POST', body: formData })
const url = commentId ? '/message-board/vote-comment/' : '/message-board/vote-post/';
fetch(`/message-board/comments/${postId}/`)
fetch('/message-board/create-comment/', {
```

**Safe tenant rewrite:** guard all tenant AJAX routes with `@family_member_required`; set `family=tenant_context.family` when creating posts, comments, and votes. Fetch posts/comments/votes with `family=tenant_context.family`; for comments, also verify `parent.post_id == post.id` and `parent.family_id == tenant_context.family.id`. Return 404 or generic JSON errors for cross-family IDs.

---

### Template Navigation And Tenant Links (component/template, request-response)

**Analog:** Phase 3 header switcher.

**Desktop tenant context pattern** (base template lines 120-146):
```django
{% if current_family and current_pool %}
<div class="relative dropdown-container" data-testid="family-context-switcher">
...
{% for choice in family_switcher_choices %}
    {% if choice.url %}
    <a ... href="{{ choice.url }}">
        <span>{{ choice.family.name }}</span>
        <span>{{ choice.pool.name }} - {{ choice.pool.season }}</span>
    </a>
    {% endif %}
{% endfor %}
```

**Mobile tenant context pattern** (base template lines 263-299):
```django
{% if current_family and current_pool %}
<div class="px-4 py-3 rounded-lg ..." data-testid="family-context-switcher">
    <div>Current family</div>
    <div>{{ current_family.name }}</div>
    <div>{{ current_pool.name }}</div>
</div>
...
{% elif family_switcher_choices %}
<a data-testid="family-context-switcher" ... href="{% url 'family_picker' %}">
```

**Apply to Phase 4:** preserve this context visibility. Replace global desktop/mobile navigation links for private app surfaces (`/scores`, `/standings/`, `/rules/`, `/picks`, `/user/<id>/`) with tenant URLs when `current_family` and `current_pool` exist. Anonymous links may stay public where the view remains public.

---

### `pickem/pickem_homepage/tests.py` (test, tenant isolation)

**Analog:** Phase 3 route, invite, decorator, and family-scope tests.

**Tenant fixture pattern** (lines 117-135):
```python
def _family_with_pool(self, name, slug, *, is_default=True):
    family = Family.objects.create(name=name, slug=slug)
    pool = Pool.objects.create(
        family=family,
        name="Main Pickem",
        slug="main",
        season=2526,
        competition="nfl",
        is_default=is_default,
    )
    return family, pool
```

**Legacy redirect assertion pattern** (lines 167-181):
```python
self.client.force_login(self.user)
response = self.client.get("/")
self.assertRedirects(
    response,
    reverse("family_pool_home", kwargs={"family_slug": family.slug, "pool_slug": pool.slug}),
    fetch_redirect_response=False,
)
```

**Negative outsider pattern** (lines 212-224):
```python
self.client.force_login(self.outsider)
response = self.client.get(reverse("family_pool_home", kwargs={"family_slug": family.slug, "pool_slug": pool.slug}))
self.assertEqual(response.status_code, 404)
```

**Role/guard unit pattern** (lines 922-950):
```python
@family_member_required(minimum_role=minimum_role)
def guarded_view(request, family_slug, pool_slug):
    return HttpResponse(request.tenant_context.membership.role)
...
with self.assertRaises(Http404):
    self._view()(self._request(self.outsider), "smith-family", "main")
```

**AJAX/security negative pattern** (lines 761-839):
```python
for raw_code, _case in cases:
    with self.subTest(raw_code=raw_code):
        response = self.client.post(self._join_url(), {"code": raw_code})
        self.assertContains(response, "Invite code is invalid or unavailable.")
        self.assertNotContains(response, "Smith Family")
        self.assertFalse(FamilyMembership.objects.filter(user=self.joiner).exists())
```

**Apply to Phase 4:** add tests proving family A members cannot access family B picks, standings, profile stats, player lists, posts, comments, votes, or pick edit IDs by changing URL slugs, object IDs, query params, or request bodies. Include positive tests for same-family access and legacy signed-in redirects.

## Shared Patterns

### Authentication And Tenant Guard
**Source:** `pickem/pickem_homepage/authz.py` lines 16-40  
**Apply to:** all tenant gameplay/community/profile/rules pages and AJAX endpoints.
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

### Canonical Tenant Resolution
**Source:** `pickem/pickem_api/authz.py` lines 175-204  
**Apply to:** helpers, context processors, tests, and any view that must resolve current family/pool.
```python
def require_tenant_context(user, *, family, pool=None, minimum_role=FamilyMembership.Role.MEMBER) -> TenantContext:
    resolved_family = resolve_family(family)
    resolved_pool = None
    if pool is not None:
        resolved_pool = resolve_pool_context(pool=pool, family=resolved_family)
    membership = require_family_membership(user, resolved_family, minimum_role=minimum_role)
    return TenantContext(family=resolved_family, pool=resolved_pool, membership=membership)
```

### Pool-Scoped Competition Data
**Source:** `pickem/pickem_api/models.py` lines 357-389 and 391-490  
**Apply to:** picks, scores overlays, standings, profile stats, weekly winners.
```python
class GamePicks(models.Model):
    pool = models.ForeignKey(Pool, on_delete=models.SET_NULL, related_name='game_picks', blank=True, null=True)
    ...
    class Meta:
        indexes = [
            models.Index(fields=['pool', 'gameseason'], name='gp_pool_season_idx'),
            models.Index(fields=['pool', 'gameseason', 'gameWeek'], name='gp_pool_season_week_idx'),
            models.Index(fields=['pool', 'userID'], name='gp_pool_userid_idx'),
        ]
```

### Family-Scoped Community Data
**Source:** `pickem/pickem_homepage/models.py` lines 100-125, 148-173, 203-226  
**Apply to:** message board posts/comments/votes and profile post counts.
```python
family = models.ForeignKey(
    "pickem_api.Family",
    on_delete=models.SET_NULL,
    related_name='message_board_posts',
    blank=True,
    null=True,
)
...
models.Index(fields=['family', 'is_active', 'created_at'], name='post_family_active_idx')
```

### Server-Owned Tenant Writes
**Source:** `pickem/pickem_homepage/views.py` lines 257-324  
**Apply to:** pick submission/edit and message-board create/comment/vote.
```python
if request.method == 'POST' and form.is_valid():
    with transaction.atomic():
        family = Family.objects.create(...)
        pool = Pool.objects.create(...)
        membership = FamilyMembership.objects.create(...)
...
return redirect('family_pool_home', family_slug=family.slug, pool_slug=pool.slug)
```

Use the same principle, not the same fields: derive tenant, user, season/week/game, and scoped ownership server-side inside the guarded view.

### Context Processor Safety
**Source:** `pickem/pickem/context_processors.py` lines 97-146  
**Apply to:** template-wide navigation and current family/pool display.
```python
context = {
    'current_family': None,
    'current_pool': None,
    'current_membership': None,
    'family_switcher_choices': [],
    'has_family_memberships': False,
}
...
tenant_context = require_tenant_context(request.user, family=family_slug, pool=pool_slug)
```

Do not trust route kwargs in templates; use this context or `request.tenant_context` after server-side authorization.

## No Analog Found

No Phase 4 file category lacks an existing analog. The codebase already has route patterns, tenant guards, scoped domain fields, legacy gameplay views, message-board AJAX, template navigation, and Django integration tests. The planner should prefer adapting these in place over introducing new frameworks or large service layers.

## Patterns To Avoid

- Do not use `allow_legacy_default=True` for new Phase 4 tenant routes.
- Do not render signed-in legacy private pages with global picks, standings, profiles, or message-board data.
- Do not trust `GamePicksForm` fields for tenant/user/game ownership; current fields include `id`, `userEmail`, `userID`, `uid`, `gameseason`, `gameWeek`, `pick_game_id`, and `pick_correct`.
- Do not filter message board rows by object ID alone. Always include `family=tenant_context.family`.
- Do not filter picks, standings, weekly winners, or profile stats by user/season alone. Always include `pool=tenant_context.pool`.
- Do not use commissioner/superuser status as a cross-family bypass.
- Do not add rules/settings editing in Phase 4; display tenant settings only.
- Do not broaden Tailwind/Bootstrap migration. Keep template edits focused on tenant links, context, and data privacy.

## Metadata

**Analog search scope:** `pickem/pickem_homepage`, `pickem/pickem_api`, `pickem/pickem`, Phase 3 summaries and patterns  
**Files scanned:** 30+ source/template/test/planning files  
**Pattern extraction date:** 2026-06-29

## PATTERNS COMPLETE
