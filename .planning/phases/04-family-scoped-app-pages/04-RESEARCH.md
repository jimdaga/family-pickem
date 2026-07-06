# Phase 04: Family-Scoped App Pages - Research

**Researched:** 2026-06-29  
**Domain:** Django tenant-scoped browser routes, page data isolation, AJAX privacy, and route compatibility  
**Confidence:** HIGH for codebase findings; MEDIUM for external Django documentation citations

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Tenant URL migration

- **D-01:** Phase 4 should migrate gameplay pages to explicit tenant URLs under `/families/<family_slug>/pools/<pool_slug>/...`.
- **D-02:** Legacy signed-in gameplay routes should redirect to the user's current/default family pool route when the user has a resolvable tenant context.
- **D-03:** Legacy routes should not continue rendering private global gameplay data for signed-in users.
- **D-04:** Anonymous behavior for public/marketing routes may remain public where it already exists, but private gameplay surfaces require authentication and tenant membership.

### Picks and scores behavior

- **D-05:** NFL games, weeks, teams, scores, and schedule reference data remain global.
- **D-06:** Picks, pick counts, "my pick" state, lock/edit state, and any pool/player overlays on score/game pages must be scoped to the current pool.
- **D-07:** Pick submission and edit paths must derive user, family, pool, season/week/game, and correctness-related fields server-side. Client-provided identifiers must be validated against server-resolved tenant context.
- **D-08:** Scores pages may show global NFL game facts, but must not show picks, pick totals, player overlays, or private context from another family/pool.

### Dashboard and standings data boundaries

- **D-09:** Tenant dashboard/home should show only current family/default pool data: current pool standings, weekly winners, pick status, family message preview, and member activity for that family/pool.
- **D-10:** Existing global standings, global league accuracy, global message-board previews, and global pick counts must either be removed from tenant pages or rewritten to be family/pool scoped.
- **D-11:** Standings and weekly winner pages should read from the current pool scope and should deny or redirect legacy global access for signed-in users.
- **D-12:** Cache keys, memoized data, and any derived/precomputed standings used in Phase 4 must include pool/family scope or be avoided until Phase 6 hardening.

### Profiles, players, and message board privacy

- **D-13:** Player lists, member profiles, profile stats, posts, comments, and votes are family-private in Phase 4.
- **D-14:** Active family membership is required before viewing another user's profile or player stats in a family context.
- **D-15:** Profile/stat views should show stats scoped to the requested family/pool context where applicable, not a user's global cross-family picks.
- **D-16:** Message-board posts, comments, votes, create/edit/delete/read endpoints, and AJAX serialization must filter by family/pool scope and deny outsiders.
- **D-17:** Negative tests must prove a member of family A cannot see family B posts, comments, votes, player list, profile stats, or pick data by changing URLs, IDs, query params, or request bodies.

### Rules display

- **D-18:** Phase 4 should make rules pages tenant-aware and display the current family/pool rules/settings in context.
- **D-19:** Rules/settings editing remains Phase 5. Phase 4 should not introduce owner/admin editing forms unless required to remove a data leak.
- **D-20:** A display-only rules page may use existing static rules as fallback copy, but route/context/data access must still be tenant-scoped.

### Route and UX behavior

- **D-21:** Tenant page links in the header, family switcher, dashboard, scores, standings, picks, rules, profiles, and message board should preserve explicit family/pool context.
- **D-22:** Empty states should stay inside the current family/pool context and avoid sending users to global data pages.
- **D-23:** 403/404/not-found behavior should avoid leaking whether another family/pool/profile/post exists where practical.
- **D-24:** Mobile navigation and header context from Phase 3 should remain visible on the migrated pages.

### the agent's Discretion

- Exact plan split and migration order, provided high-risk private data paths are migrated before polish-only work.
- Exact tenant route names, template filenames, partial extraction, and helper names, provided URLs remain readable and explicit.
- Exact dashboard widget composition, provided it only uses current family/pool data.
- Whether to implement small compatibility redirects per route or a shared helper, provided behavior is tested.

### Deferred Ideas (OUT OF SCOPE)

- Owner/admin editing of rules and family/pool settings remains Phase 5.
- Full invite management, revocation/regeneration UI, role management, member management, and audit-log UI remain Phase 5.
- Cron/scoring production hardening and background pool-aware scoring job changes remain Phase 6 unless Phase 4 research finds a tiny route-adjacent blocker.
- Multi-active-pool UI remains v2/advanced pool scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTHZ-02 | Every family/pool write path checks authenticated membership server-side. | Tenant AJAX and pick write routes must use `family_member_required` and derive `pool`, `user`, and game fields server-side. [VERIFIED: codebase grep] |
| AUTHZ-04 | Outsiders cannot view or infer private family picks, standings, members, dashboards, profiles, or message-board data. | Current legacy views still query global `GamePicks`, `userSeasonPoints`, `userStats`, and message-board rows; tenant routes must filter by `pool` or `family`. [VERIFIED: codebase grep] |
| AUTHZ-05 | Client-provided family, pool, user, season, week, and game identifiers are validated against server-resolved membership and allowed objects. | `GamePicksForm` currently exposes server-owned fields including user IDs, game identifiers, season/week, correctness, and tiebreakers. [VERIFIED: codebase grep] |
| POOL-03 | Scores can use global NFL game data while showing only pool-scoped pick overlays. | `GamesAndScores`, `GameWeeks`, and `Teams` have no tenant key, while `GamePicks` and `userSeasonPoints` have nullable `pool` FKs added in Phase 1. [VERIFIED: codebase grep] |
| POOL-04 | Rules/settings are visible and editable in the appropriate family/pool context. | Phase 4 should implement display-only `PoolSettings` context; editing remains Phase 5 per locked decision D-19. [VERIFIED: 04-CONTEXT.md] |
| COMM-02 | Family members can see member/profile stats only within allowed family context. | `user_profile()` currently reads global season points, stats, picks, and posts by `user_id` without membership checks. [VERIFIED: codebase grep] |
| SEC-03 | Cross-family isolation has automated negative tests. | Existing tests cover Phase 3 tenant entry and invite paths; Phase 4 needs negative tests for each migrated page/AJAX endpoint. [VERIFIED: codebase grep] |
| SEC-04 | Cache keys and precomputed data are family/pool scoped. | No explicit page cache was found, but footer/context and `current_rank`/denormalized standings reads are currently global and must include `pool`. [VERIFIED: codebase grep] |
</phase_requirements>

## Summary

Phase 4 should migrate the existing Django function-based gameplay and community pages into explicit tenant routes under `/families/<family_slug>/pools/<pool_slug>/...`, using the already-established `family_member_required` decorator and `request.tenant_context`. [VERIFIED: codebase grep] The highest-risk work is not template polish; it is removing global reads and writes from `index`, `scores`, `scores_long`, `standings`, `submit_game_picks`, `edit_game_pick`, `user_profile`, and message-board AJAX endpoints. [VERIFIED: codebase grep]

The standard implementation path is to keep global NFL reference queries for games/weeks/teams, but wrap every private overlay in `pool=tenant_context.pool` or `family=tenant_context.family`. [VERIFIED: SECURITY_THREAT_MODEL.md] Signed-in legacy gameplay routes should be compatibility redirects into the user's default/current pool route, while anonymous public routes may keep existing public behavior only where they do not render private app data. [VERIFIED: 04-CONTEXT.md]

**Primary recommendation:** Implement tenant routes plus shared redirect and query helpers first, then migrate data surfaces in this order: picks writes, message-board AJAX, scores overlays, standings/dashboard, profiles/players, rules display-only, shared navigation/footer context. [VERIFIED: codebase grep]

## Project Constraints (from AGENTS.md)

- Use Django ORM for database queries and avoid raw SQL. [VERIFIED: AGENTS.md]
- Follow Django naming conventions: models in `CamelCase`, views/functions in `snake_case`. [VERIFIED: AGENTS.md]
- Browser validation should use the already-running local server at `http://localhost:8000`; do not start it unnecessarily. [VERIFIED: AGENTS.md]
- Use `curl http://localhost:8000` to inspect rendered HTML when validating page changes. [VERIFIED: AGENTS.md]
- CSS/template changes must account for JavaScript-driven DOM changes. [VERIFIED: AGENTS.md]
- The app is mid Bootstrap-to-Tailwind migration; keep Phase 4 UI edits focused and avoid broad visual rewrites. [VERIFIED: AGENTS.md]
- Run Django tests from `pickem` with `python manage.py test`; use `pickem.test_settings` for isolated project tests. [VERIFIED: AGENTS.md]
- Current season must be read via `pickem.utils.get_season()` or database-backed current season behavior, not hardcoded. [VERIFIED: AGENTS.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tenant URL resolution and denial behavior | Frontend Server (Django views) | API / Backend auth helpers | Browser routes already resolve slugs through `family_member_required`, which delegates to `require_tenant_context()`. [VERIFIED: codebase grep] |
| Picks submit/edit privacy | Frontend Server (Django views) | Database / Storage | Session user and route tenant must determine the saved `GamePicks.pool`, user fields, and game fields; the database stores pool scope. [VERIFIED: codebase grep] |
| Scores page NFL facts | Database / Storage | Frontend Server | `GamesAndScores`, `GameWeeks`, and `Teams` are global reference data queried by season/week/competition. [VERIFIED: codebase grep] |
| Scores pick overlays | Frontend Server (Django views) | Database / Storage | Overlay counts, my-pick state, player rows, and weekly points must be filtered by `pool`. [VERIFIED: 04-CONTEXT.md] |
| Standings/dashboard widgets | Frontend Server (Django views) | Database / Storage | Existing pages aggregate `userSeasonPoints`, `GamePicks`, and message-board rows in views; Phase 4 should scope those querysets before rendering. [VERIFIED: codebase grep] |
| Profiles/players privacy | Frontend Server (Django views) | Database / Storage | Profile route must verify current family membership for viewer and viewed user before reading pool-scoped stats. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| Message board/AJAX privacy | Frontend Server (Django views) | Database / Storage | Post/comment/vote IDs are global primary keys, so each endpoint must resolve target rows through the current family. [VERIFIED: codebase grep] |
| Rules display | Frontend Server (Django views) | Database / Storage | Display can reuse static copy but should include `PoolSettings` for the current pool. [VERIFIED: codebase grep] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 4.0.2 | URL routing, function views, templates, ORM, auth decorators, CSRF middleware. | Existing project framework and installed runtime. [VERIFIED: local python import] |
| Django REST Framework | 3.13.1 | Existing API layer and tenant proof endpoint patterns. | Existing API framework; Phase 4 is mostly browser views but tests may touch API guards. [VERIFIED: local python import] |
| django-allauth | 0.51.0 | Google OAuth/session login. | Existing authentication integration. [VERIFIED: local python import] |
| Tailwind CSS | 3.4.18 | Existing template styling during migration. | Installed in `package.json`; keep edits compatible with current templates. [VERIFIED: codebase grep] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| django-ratelimit | 4.1.0 | Existing rate-limit package. | Do not make rate-limiting a Phase 4 dependency; production hardening is later. [VERIFIED: requirements.txt] |
| psycopg2-binary | 2.9.3 | PostgreSQL driver. | No direct Phase 4 use beyond ORM-backed tests. [VERIFIED: requirements.txt] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Function-based tenant views | Class-based views | Existing app uses function views; switching style would add migration risk without improving isolation. [VERIFIED: codebase grep] |
| Direct scoped ORM helpers in `views.py` | New service layer | Small local helpers are enough for Phase 4; a service layer may be useful later if cron/API hardening expands. [ASSUMED] |

**Installation:** No new packages should be installed for Phase 4. [VERIFIED: codebase grep]

## Package Legitimacy Audit

No external packages are recommended for installation in this phase. [VERIFIED: codebase grep]

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| None | — | — | — | — | — | No install |

**Packages removed due to [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```text
Browser request
  |
  v
Legacy route? (/picks/, /scores/, /standings/, /rules/, /user/<id>/, message-board/*)
  |
  +-- anonymous and public-safe route -> existing public rendering only when no private overlays are included
  |
  +-- signed-in -> resolve active/default family pool -> redirect to explicit tenant URL
                                                |
                                                v
/families/<family_slug>/pools/<pool_slug>/<page>/
  |
  v
family_member_required -> require_tenant_context(user, family_slug, pool_slug)
  |
  +-- unauthenticated -> login redirect
  +-- non-member/inactive/bad slug -> 404
  +-- wrong role for owner/admin route -> 403
  |
  v
Tenant-scoped view helpers
  |
  +-- global NFL facts: GamesAndScores/GameWeeks/Teams by season/week/competition
  +-- pool private data: GamePicks/userSeasonPoints/userStats by pool
  +-- family private data: MessageBoardPost/Comment/Vote and members by family
  |
  v
Template or JsonResponse with tenant-preserving links and AJAX URLs
```

### Recommended Project Structure

```text
pickem/pickem_homepage/
├── urls.py              # add tenant page and tenant AJAX route names; keep legacy redirects
├── views.py             # keep function views; add scoped helpers near related views
├── forms.py             # replace broad GamePicksForm usage with narrow input validation
├── templates/pickem/    # update links/forms/scripts to tenant route names
└── tests.py             # add Phase 4 positive and cross-family negative tests
```

### Pattern 1: Tenant Route Wrapper

**What:** Add tenant-specific routes and decorate each private route with `@family_member_required`. [VERIFIED: codebase grep]  
**When to use:** All gameplay/community pages and AJAX endpoints that read/write family or pool data. [VERIFIED: 04-CONTEXT.md]

```python
# Source: existing pickem_homepage.authz + Django URL dispatcher docs
@family_member_required
def tenant_scores(request, family_slug, pool_slug):
    tenant = request.tenant_context
    games = GamesAndScores.objects.filter(
        gameseason=tenant.pool.season,
        competition=tenant.pool.competition,
    )
    picks = GamePicks.objects.filter(pool=tenant.pool)
```

Django URL patterns route captured path values as view keyword arguments, and named URL reversing should be used for templates/redirects. [CITED: https://docs.djangoproject.com/en/4.0/topics/http/urls/]

### Pattern 2: Legacy Redirect Helper

**What:** Signed-in legacy private routes redirect to the user's default active pool URL; no private global data should render on legacy paths. [VERIFIED: 04-CONTEXT.md]  
**When to use:** `/scores/`, long scores route, `/standings/`, `/rules/`, `/picks/`, `/picks/edit/`, `/user/<id>/`, and message-board endpoints where a tenant context is absent. [VERIFIED: codebase grep]

```python
def redirect_to_default_pool_route(request, route_name, **extra_kwargs):
    choices = get_family_pool_choices(request.user)
    if not choices:
        return redirect('onboarding')
    if len(choices) > 1:
        return redirect('family_picker')
    choice = choices[0]
    return redirect(route_name, family_slug=choice['family'].slug, pool_slug=choice['pool'].slug, **extra_kwargs)
```

Django `redirect()` accepts a view name and arguments and returns an HTTP redirect response. [CITED: https://docs.djangoproject.com/en/4.0/topics/http/shortcuts/]

### Pattern 3: Server-Derived Pick Writes

**What:** Treat POST data as only the selected team and optional tiebreakers; derive `pool`, `userEmail`, `userID`, `uid`, `slug`, `competition`, `gameseason`, `gameWeek`, `gameyear`, `pick_game_id`, and `pick_correct` from `request.user`, `request.tenant_context`, and the resolved game. [VERIFIED: SECURITY_THREAT_MODEL.md]  
**When to use:** `submit_game_picks` and `edit_game_pick`. [VERIFIED: codebase grep]

### Pattern 4: Scoped Object Lookup

**What:** Use `get_object_or_404()` with tenant filters, not a global object lookup followed by an authorization check. [CITED: https://docs.djangoproject.com/en/4.0/topics/http/shortcuts/]  
**When to use:** message-board post/comment/vote targets, profile users within family membership, picks by ID, and standings/profile rows by pool. [VERIFIED: codebase grep]

```python
post = get_object_or_404(
    MessageBoardPost,
    id=post_id,
    family=tenant.family,
    is_active=True,
)
```

### Anti-Patterns to Avoid

- **Global query plus tenant label:** Adding `family` to context while leaving `GamePicks.objects.filter(gameseason=...)` unscoped still leaks private data. [VERIFIED: codebase grep]
- **Hidden tenant form fields:** The security model explicitly says not to rely on hidden form fields or client-provided tenant/user IDs. [VERIFIED: SECURITY_THREAT_MODEL.md]
- **Global object IDs in AJAX endpoints:** Current message-board endpoints fetch by post/comment ID only; tenant routes must include route context and scoped lookup. [VERIFIED: codebase grep]
- **Broad UI rewrite:** Phase 4 should preserve the mid-migration Tailwind/Bootstrap templates and prioritize privacy behavior. [VERIFIED: AGENTS.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tenant membership resolution | Per-view ad hoc slug/user checks | `family_member_required` and `require_tenant_context()` | Existing helpers already encode active membership, pool-family consistency, and denial semantics. [VERIFIED: codebase grep] |
| Route URL string construction | Manual `f"/families/{slug}/..."` in views/templates | Django named routes and `reverse`/`{% url %}` | Named reversing is the framework pattern and avoids stale links during migration. [CITED: https://docs.djangoproject.com/en/4.0/topics/http/urls/] |
| JSON responses | Manual JSON string serialization | `JsonResponse` | Existing views use `JsonResponse`; Django provides the response type. [CITED: https://docs.djangoproject.com/en/4.0/ref/request-response/#jsonresponse-objects] |
| CSRF for session AJAX | Custom token schemes | Django CSRF middleware and `{% csrf_token %}`/`X-CSRFToken` | Django documents CSRF middleware/decorator support for unsafe methods. [CITED: https://docs.djangoproject.com/en/4.0/ref/csrf/] |
| Scoped row existence handling | Global `get()` then custom errors | `get_object_or_404()` with tenant filters | Avoids leaking existence through distinct unauthorized errors. [CITED: https://docs.djangoproject.com/en/4.0/topics/http/shortcuts/] |

**Key insight:** The hard part is not rendering new URLs; it is ensuring every read/write path can only reach rows through `request.tenant_context`. [VERIFIED: SECURITY_THREAT_MODEL.md]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Tenant FKs already exist but remain nullable: `GamePicks.pool`, `userSeasonPoints.pool`, `userStats.pool`, and message-board `family`; existing legacy rows are backfilled per prior summaries. [VERIFIED: prior summaries + codebase grep] | Code edit only in Phase 4; no data migration unless tests discover unscoped newly-created rows from current forms. |
| Live service config | No repo-managed external route config was found beyond Django URLs and Docker compose. [VERIFIED: codebase grep] | Update in-app URLs/templates; production ingress/router changes are not indicated for these internal paths. |
| OS-registered state | No launchd/systemd/pm2 task definitions were found in the repo. [VERIFIED: codebase grep] | None for Phase 4. |
| Secrets/env vars | Environment variables relate to Django secret, DB, Google OAuth, allowed hosts, CSRF origins, S3, and DEBUG; no route-specific secret keys were found. [VERIFIED: AGENTS.md + codebase grep] | None for Phase 4. |
| Build artifacts | Tailwind output exists at `pickem_homepage/static/css/tailwind.css`; Phase 4 should not require a CSS build unless template classes change. [VERIFIED: codebase grep] | If CSS classes are changed, run `npm run build:prod`; otherwise skip. |

**Nothing found in category:** OS-registered route state was not found by `find`/`rg`; stored database rows exist but require query/write scoping rather than a Phase 4 data migration. [VERIFIED: codebase grep]

## Current Code Findings

| Surface | Current Behavior | Phase 4 Planning Implication |
|---------|------------------|------------------------------|
| `urls.py` | Only tenant pool home and invite routes exist; scores, standings, rules, picks, profile, and message-board routes are still legacy/global. [VERIFIED: codebase grep] | Add tenant route names for every migrated page and AJAX endpoint. |
| `index()` | Anonymous renders public home; signed-in users redirect to onboarding/default pool/picker; anonymous public home still computes global standings, pick counts, and message-board data. [VERIFIED: codebase grep] | Build tenant dashboard from `family_pool_home` or a new tenant dashboard helper; keep anonymous marketing content free of private widgets. |
| `family_pool_home()` | Currently a shell with links back to `/picks/`, `/standings/`, and `/scores/`. [VERIFIED: codebase grep] | Replace with tenant dashboard widgets and tenant links. |
| `scores()` / `scores_long()` | Game facts are global, but picks, points, players, week winners, and user weekly stats are global by season/week/competition. [VERIFIED: codebase grep] | Keep game query global; filter all overlay querysets by `pool`. |
| `standings()` | Reads all seasons from games and `userSeasonPoints` by season only. [VERIFIED: codebase grep] | Filter `userSeasonPoints` by `pool`; season choices should be constrained to current pool/competition policy. |
| `submit_game_picks()` | GET is anonymous-friendly; POST saves `GamePicksForm` with client-owned model fields. [VERIFIED: codebase grep] | Tenant page must require login/member and save server-derived fields. |
| `edit_game_pick()` | Requires login and matches pick by `id` plus `userEmail`; no pool filter. [VERIFIED: codebase grep] | Tenant AJAX route must include `pool=tenant.pool` and validate game belongs to pool season/competition. |
| `user_profile()` | Public route reads global stats, picks, rankings, posts, and includes debug `print()` statements. [VERIFIED: codebase grep] | Add tenant profile/player route and deny non-shared-family access; remove debug prints when touched. |
| Message board AJAX | Post/comment/vote/read endpoints use global IDs and create rows without `family`. [VERIFIED: codebase grep] | Move under tenant URL, require family member, scope target lookups, and write `family=tenant.family`. |
| Shared context | `footer_stats_context` computes rank and weekly correct picks without pool. [VERIFIED: codebase grep] | Include current tenant pool when available or suppress private stats outside tenant context. |
| `site_banner_context` | `SiteBanner.get_active_banner()` returns highest-priority active banner without family filtering. [VERIFIED: codebase grep] | If banners are shown on tenant pages, prefer `family=current_family OR family IS NULL` with defined priority. |

## Common Pitfalls

### Pitfall 1: Redirecting Page Routes But Leaving AJAX Global

**What goes wrong:** The visible page is tenant-scoped, but JavaScript still posts to `/message-board/create-post/`, `/picks/edit/`, or fetches `/message-board/comments/<id>/`. [VERIFIED: codebase grep]  
**Why it happens:** Current templates hardcode legacy AJAX URLs. [VERIFIED: codebase grep]  
**How to avoid:** Put tenant AJAX endpoint URLs in template context or `data-*` attributes generated with `{% url %}`. [VERIFIED: codebase grep]  
**Warning signs:** Negative tests pass for GET pages but fail for POST/fetch endpoints. [ASSUMED]

### Pitfall 2: Pool-Scoped Standings With Global Rank

**What goes wrong:** `player_points` is filtered by `pool`, but `current_rank`, footer rank, or profile best rank still counts global rows. [VERIFIED: codebase grep]  
**Why it happens:** Rank fields and profile calculations are denormalized and currently query by `gameseason` only. [VERIFIED: codebase grep]  
**How to avoid:** For Phase 4, compute/display ranks from the current pool queryset or hide rank widgets until pool-scoped data is available. [VERIFIED: 04-CONTEXT.md]  
**Warning signs:** Family A page shows ranks larger than Family A membership count. [ASSUMED]

### Pitfall 3: Client-Owned Pick Fields

**What goes wrong:** A user forges hidden fields and writes picks for another user, pool, week, game, or correctness state. [VERIFIED: SECURITY_THREAT_MODEL.md]  
**Why it happens:** `GamePicksForm` exposes almost every `GamePicks` field. [VERIFIED: codebase grep]  
**How to avoid:** Replace model-form save with explicit validation and `update_or_create`/create logic using server-resolved fields. [VERIFIED: codebase grep]  
**Warning signs:** Tests can submit `uid` or `pick_correct=True` and the saved row preserves it. [VERIFIED: codebase grep]

### Pitfall 4: Existence Leakage Through Error Messages

**What goes wrong:** Non-members learn another family/post/profile exists from different 403/404 or raw exception text. [VERIFIED: SECURITY_THREAT_MODEL.md]  
**Why it happens:** Current JSON endpoints often return `str(e)`. [VERIFIED: codebase grep]  
**How to avoid:** Use scoped `get_object_or_404()` and generic JSON error messages for unavailable targets. [CITED: https://docs.djangoproject.com/en/4.0/topics/http/shortcuts/]

## Code Examples

### Tenant URL Patterns

```python
# Source: Django URL dispatcher docs + existing route shape
path(
    'families/<slug:family_slug>/pools/<slug:pool_slug>/scores/',
    views.tenant_scores,
    name='tenant_scores',
)
path(
    'families/<slug:family_slug>/pools/<slug:pool_slug>/message-board/comments/<int:post_id>/',
    views.tenant_get_post_comments,
    name='tenant_get_post_comments',
)
```

### Scoped Message Board Lookup

```python
# Source: Django shortcuts docs + current MessageBoardPost model
@family_member_required
@require_http_methods(["POST"])
def tenant_create_comment(request, family_slug, pool_slug):
    tenant = request.tenant_context
    data = json.loads(request.body)
    post = get_object_or_404(
        MessageBoardPost,
        id=data.get('post_id'),
        family=tenant.family,
        is_active=True,
    )
    comment = MessageBoardComment.objects.create(
        family=tenant.family,
        post=post,
        user=request.user,
        content=data.get('content', '').strip(),
    )
    return JsonResponse({'success': True, 'comment_id': comment.id})
```

### Pool-Scoped Pick Edit

```python
# Source: current edit_game_pick plus Phase 4 tenant constraint
existing_pick = get_object_or_404(
    GamePicks,
    id=pick_id,
    pool=request.tenant_context.pool,
    uid=request.user.id,
)
game = get_object_or_404(
    GamesAndScores,
    id=existing_pick.pick_game_id,
    gameseason=request.tenant_context.pool.season,
    competition=request.tenant_context.pool.competition,
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global gameplay pages by season/week/user | Explicit family/pool URL context with server-side membership checks | Phase 2/3 established helpers and route shell; Phase 4 completes page migration. [VERIFIED: prior summaries] | Legacy signed-in routes become redirects, not private data renderers. |
| Client posts full pick model fields | Server derives tenant/user/game fields | Required by Phase 4 decisions and threat model. [VERIFIED: 04-CONTEXT.md] | Prevents forged user/pool/correctness writes. |
| Public/global profiles and message board | Family-private by default | Phase 4 locked decisions D-13 through D-17. [VERIFIED: 04-CONTEXT.md] | AJAX endpoints and profile links need tenant context. |

**Deprecated/outdated:**
- `GamePicksForm` direct save for user-facing picks: unsafe because it accepts server-owned fields. [VERIFIED: codebase grep]
- Legacy private app links like `/picks/`, `/scores/`, `/standings/`, `/rules/`, `/user/<id>/`, and `/message-board/*` inside signed-in tenant UI: unsafe because they drop tenant context. [VERIFIED: codebase grep]
- Global `is_commissioner` routing for family administration: out of Phase 4 except avoid expanding it; Phase 5 owns admin migration. [VERIFIED: ROADMAP.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A new service layer is not necessary for Phase 4; focused helpers in `views.py` are enough. | Standard Stack | If wrong, duplication may grow and planner should split helper extraction into an early task. |
| A2 | Warning signs listed for tests are inferred from standard tenant-isolation failure modes. | Common Pitfalls | If wrong, test names may change but required negative coverage remains the same. |

## Open Questions (RESOLVED)

1. **Should tenant profiles live under pool or family route?**
   - What we know: Phase 4 says profile/stat views should show stats scoped to requested family/pool where applicable. [VERIFIED: 04-CONTEXT.md]
   - Resolution: Use the explicit pool route for Phase 4 profile/stat pages, for example `/families/<family_slug>/pools/<pool_slug>/users/<user_id>/` or the local route-name equivalent. Stats-heavy pages are pool-scoped; link text can still say "Players" or "Profile".

2. **Should anonymous `/scores/` remain public after tenant migration?**
   - What we know: Anonymous behavior for public/marketing routes may remain public, but private overlays require auth and membership. [VERIFIED: 04-CONTEXT.md]
   - Resolution: Anonymous `/scores/` may remain public only as an NFL-facts-only surface. Signed-in users should redirect to tenant scores when a current/default tenant can be resolved. No pick overlays, member links, pick counts, or "my pick" state may render without tenant membership.

3. **How should all-time/lifetime stats behave across pools?**
   - What we know: Phase 4 says profile stats should be scoped to requested family/pool where applicable. [VERIFIED: 04-CONTEXT.md]
   - Resolution: Lifetime/all-time stats in Phase 4 mean current-pool rows only, or are hidden/suppressed when they cannot be safely scoped. Cross-pool or family-wide aggregation is out of scope until a later model decision.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Django tests and app runtime | ✓ | 3.10.6 via `../venv/bin/python` | Use repository virtualenv. [VERIFIED: local command] |
| Django | App/test framework | ✓ | 4.0.2 | None. [VERIFIED: local command] |
| Django test runner | Phase verification | ✓ | Django 4.0.2 test command available | None. [VERIFIED: local command] |
| Node/npm | Tailwind rebuild if needed | ✓ | Node v25.2.1, npm 11.6.2 | Skip if no CSS build output changes. [VERIFIED: local command] |
| Local webserver | HTML curl validation | Assumed running per AGENTS.md | `http://localhost:8000` | If unavailable, use Django test client for automated verification. [VERIFIED: AGENTS.md] |

**Missing dependencies with no fallback:** none found. [VERIFIED: local command]  
**Missing dependencies with fallback:** local server availability can fall back to Django test client for automated assertions. [VERIFIED: AGENTS.md]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Django `TestCase` / Django test runner 4.0.2. [VERIFIED: local command] |
| Config file | `pickem/pickem/test_settings.py`. [VERIFIED: codebase grep] |
| Quick run command | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2` |
| Full suite command | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTHZ-02 | Tenant pick/message-board writes require active membership and write current family/pool. | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.Phase4TenantWriteTests --settings=pickem.test_settings --verbosity=2` | ❌ Wave 0 |
| AUTHZ-04 | Non-member cannot view tenant dashboard/scores/standings/picks/rules/profile/message-board data. | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.Phase4TenantPageIsolationTests --settings=pickem.test_settings --verbosity=2` | ❌ Wave 0 |
| AUTHZ-05 | Forged user/pool/family/season/week/game fields are ignored or rejected. | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.Phase4PickValidationTests --settings=pickem.test_settings --verbosity=2` | ❌ Wave 0 |
| POOL-03 | Scores show global NFL facts but only current-pool overlays. | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.Phase4ScoresScopeTests --settings=pickem.test_settings --verbosity=2` | ❌ Wave 0 |
| POOL-04 | Rules page is tenant-aware and display-only. | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.Phase4RulesScopeTests --settings=pickem.test_settings --verbosity=2` | ❌ Wave 0 |
| COMM-02 | Profiles/player stats require shared family and are pool-scoped. | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.Phase4ProfilePrivacyTests --settings=pickem.test_settings --verbosity=2` | ❌ Wave 0 |
| SEC-03 | Family A cannot access Family B private IDs through URL/query/body changes. | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.Phase4CrossFamilyNegativeTests --settings=pickem.test_settings --verbosity=2` | ❌ Wave 0 |
| SEC-04 | Shared context stats and standings data are pool-scoped or suppressed. | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.Phase4SharedContextScopeTests --settings=pickem.test_settings --verbosity=2` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings --verbosity=2`
- **Per wave merge:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2`
- **Phase gate:** `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings && cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings && cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2`

### Wave 0 Gaps

- [ ] `pickem_homepage.tests.Phase4TenantRouteTestDataMixin` — creates two families, pools, memberships, games, picks, standings, posts, comments, and votes.
- [ ] `pickem_homepage.tests.Phase4TenantPageIsolationTests` — covers tenant GET routes and legacy redirects.
- [ ] `pickem_homepage.tests.Phase4TenantWriteTests` — covers pick and message-board writes.
- [ ] `pickem_homepage.tests.Phase4ProfilePrivacyTests` — covers player/profile privacy.
- [ ] `pickem_homepage.tests.Phase4SharedContextScopeTests` — covers footer/banner/header data leakage.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Django session authentication plus `login_required`/tenant guard. [VERIFIED: codebase grep] |
| V3 Session Management | yes | Existing Django sessions; no new session mechanism in Phase 4. [VERIFIED: codebase grep] |
| V4 Access Control | yes | `require_tenant_context()`, active `FamilyMembership`, scoped ORM lookups, and 404/403 denial semantics. [VERIFIED: codebase grep] |
| V5 Input Validation | yes | Django forms/explicit validators; validate week/game/team/tiebreaker and ignore forged server-owned fields. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| V6 Cryptography | no new cryptography | Invite hashing already exists; Phase 4 should not add crypto. [VERIFIED: codebase grep] |
| V7 Error Handling | yes | Generic 404/JSON errors for inaccessible tenant objects; avoid `str(e)` in responses. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| V14 Configuration | limited | Do not alter production settings except route/view behavior; CSRF exemptions in unrelated endpoints remain hardening scope unless touched. [VERIFIED: ROADMAP.md] |

### Known Threat Patterns for Django Tenant Pages

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR/BOLA through changed slugs or IDs | Information Disclosure / Elevation of Privilege | Resolve family/pool server-side and lookup target objects with tenant filters. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| Forged hidden pick fields | Tampering | Server-derive user/pool/game/season/week/correctness fields. [VERIFIED: SECURITY_THREAT_MODEL.md] |
| Cross-family message-board fetch/vote | Information Disclosure / Tampering | Tenant AJAX routes plus family-filtered `get_object_or_404()`. [VERIFIED: codebase grep] |
| CSRF on session JSON mutations | Tampering | Use Django CSRF protection for unsafe methods; remove `csrf_exempt` if endpoints are modified in Phase 4. [CITED: https://docs.djangoproject.com/en/4.0/ref/csrf/] |
| Existence probing | Information Disclosure | Use 404 for non-members/bad tenant context and generic JSON errors. [VERIFIED: 02-CONTEXT.md] |
| Cache/precomputed standings leakage | Information Disclosure | Include `pool_id` in any cache/precomputed lookup or avoid caching in Phase 4. [VERIFIED: SECURITY_THREAT_MODEL.md] |

## Scope Boundaries

- In scope: tenant routes, legacy redirects, tenant dashboard, pool-scoped picks/scores/standings, display-only rules, family-private profiles/players, family-private message board/AJAX, tests, and shared context leak fixes. [VERIFIED: 04-CONTEXT.md]
- Out of scope: rules editing, family/admin/member management, full invite management, owner/admin settings UI, cron/scoring hardening, multi-active-pool UI, non-null FK enforcement, and production migration runbooks. [VERIFIED: 04-CONTEXT.md]
- Route-adjacent exception: if a current write path creates unscoped rows during Phase 4 tests, fix that write path in Phase 4 even if deeper cron hardening remains Phase 6. [VERIFIED: 04-CONTEXT.md]

## Sources

### Primary (HIGH confidence)

- `AGENTS.md` — project commands, Django conventions, server/curl validation, Tailwind migration constraints.
- `.planning/phases/04-family-scoped-app-pages/04-CONTEXT.md` — locked decisions, discretion, deferred scope, canonical references.
- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` — project value, phase scope, requirement traceability, current completion state.
- Prior summaries `01-02`, `01-03`, `02-01`, `02-02`, `03-01`, `03-03`, `03-04`, `03-05` — tenant schema, authz, onboarding/switcher handoff.
- `SECURITY_THREAT_MODEL.md`, `FAMILY_MULTI_TENANCY_PLAN.md`, `DISCOVERY.md`, `TEST_PLAN.md` — route/API inventory, threat model, required mitigations, negative test matrix.
- Codebase grep/read of `pickem_homepage/views.py`, `urls.py`, `forms.py`, `authz.py`, templates, `pickem_api/authz.py`, `models.py`, `context_processors.py`, and tests.

### Secondary (MEDIUM confidence)

- Django 4.0 URL dispatcher docs: https://docs.djangoproject.com/en/4.0/topics/http/urls/
- Django 4.0 shortcuts docs: https://docs.djangoproject.com/en/4.0/topics/http/shortcuts/
- Django 4.0 CSRF docs: https://docs.djangoproject.com/en/4.0/ref/csrf/
- Django 4.0 `JsonResponse` docs: https://docs.djangoproject.com/en/4.0/ref/request-response/#jsonresponse-objects

### Tertiary (LOW confidence)

- Assumptions A1-A2 only; no package recommendations depend on them.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified from requirements/local imports/package.json.
- Architecture: HIGH — based on existing Phase 2/3 helpers and source routes/views.
- Pitfalls: HIGH for code-backed pitfalls; LOW only for inferred warning signs.
- External Django patterns: MEDIUM — cited from official Django 4.0 documentation using web lookup after Context7 was unavailable in this runtime.

**Research date:** 2026-06-29  
**Valid until:** 2026-07-29 for codebase-specific planning; re-check if Django dependencies or tenant schema change.

## RESEARCH COMPLETE
