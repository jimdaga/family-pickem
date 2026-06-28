<!-- refreshed: 2026-06-28 -->
# Architecture

**Analysis Date:** 2026-06-28

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                  HTTP / Browser / Cron Jobs                  │
├──────────────────┬──────────────────┬───────────────────────┤
│ Template Pages   │ REST API         │ Scheduled Scripts      │
│ `pickem_homepage`│ `pickem_api`     │ `pickem_api/cron_*.py` │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Django Views, Forms, Serializers                │
│ `pickem_homepage/views.py`, `pickem_api/views.py`,           │
│ `pickem_homepage/forms.py`, `pickem_api/serializers.py`      │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Django ORM Models                         │
│ `pickem_api/models.py`, `pickem_homepage/models.py`          │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL, static assets, Google OAuth, ESPN APIs, Helm     │
│ `pickem/pickem/settings.py`, `charts/family-pickem/`         │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Django project config | Root URL routing, installed apps, middleware, templates, database, DRF, OAuth, static storage | `pickem/pickem/settings.py`, `pickem/pickem/urls.py` |
| Homepage app | Template-rendered pages, picks UI, standings UI, profiles, message board AJAX, commissioner dashboard | `pickem/pickem_homepage/views.py`, `pickem/pickem_homepage/urls.py` |
| API app | JSON endpoints for games, weeks, teams, picks, user points, seasons | `pickem/pickem_api/views.py`, `pickem/pickem_api/urls.py` |
| League models | Games, teams, picks, week schedules, user season points, stats, current season, user profile | `pickem/pickem_api/models.py` |
| Community models | Site banners, message-board posts, nested comments, votes | `pickem/pickem_homepage/models.py` |
| Forms | Model forms and command forms for picks, message board, week winners, banners | `pickem/pickem_homepage/forms.py` |
| Serializers | DRF serializers around API-owned models and Django users | `pickem/pickem_api/serializers.py` |
| Template helpers | Django filters and tags for user lookup, logos, stats, pick locks, dict lookup, message icons | `pickem/pickem_homepage/templatetags/pickem_homepage_extras.py` |
| Shared utilities | Season lookup and pick-lock timing rules | `pickem/pickem/utils.py` |
| Global template context | Theme, active site banner, footer stats, commissioner flag | `pickem/pickem/context_processors.py` |
| Scheduled data updates | ESPN data ingestion and scoring through local API endpoints | `pickem/pickem_api/cron_update_games_v2.py`, `pickem/pickem_api/cron_update_picks.py`, `pickem/pickem_api/cron_update_standings.py`, `pickem/pickem_api/cron_update_records.py` |
| Deployment | Docker image, Helm deployment, Kubernetes CronJob, ArgoCD manifests | `docker/app/Dockerfile`, `charts/family-pickem/templates/deployment.yaml`, `charts/family-pickem/templates/cronjob.yaml`, `infra/argocd/applications/` |

## Pattern Overview

**Overall:** Two-app Django monolith with function-based template views, function-based DRF endpoints, ORM models, and API-driven background scripts.

**Key Characteristics:**
- Route browser pages through `pickem_homepage.urls` from `pickem/pickem/urls.py`.
- Route machine-readable endpoints through `pickem_api.urls` under `/api/`.
- Keep league domain data in `pickem_api.models`; keep site/community-only data in `pickem_homepage.models`.
- Use Django ORM directly inside views and template filters; there is no separate service layer.
- Use cron scripts as external clients of the same REST API, not as Django management commands.
- Use Tailwind-generated CSS from `pickem/pickem_homepage/static/css/input.css` to `pickem/pickem_homepage/static/css/tailwind.css`.

## Layers

**Project Shell:**
- Purpose: Configure Django, route top-level URLs, expose WSGI/ASGI, and run management commands.
- Location: `pickem/pickem/`, `pickem/manage.py`
- Contains: `settings.py`, `urls.py`, `wsgi.py`, `asgi.py`, `utils.py`, `context_processors.py`
- Depends on: Django, DRF, django-allauth, django-storages, app modules.
- Used by: Local runserver, Docker entrypoint, tests, WSGI/ASGI servers.

**Template UI Layer:**
- Purpose: Render pages and handle form/AJAX workflows for users.
- Location: `pickem/pickem_homepage/`
- Contains: `views.py`, `urls.py`, `forms.py`, `models.py`, `templates/pickem/*.html`, `templatetags/pickem_homepage_extras.py`, static CSS/images.
- Depends on: `pickem_api.models`, `pickem.utils`, Django auth, django-allauth social accounts.
- Used by: Browser routes such as `/`, `/scores/`, `/standings/`, `/picks/`, `/profile/`, `/commissioners/`.

**API Layer:**
- Purpose: Provide JSON CRUD-style access to games, weeks, picks, teams, season points, and current season.
- Location: `pickem/pickem_api/`
- Contains: `views.py`, `urls.py`, `serializers.py`, `permissions.py`, `models.py`.
- Depends on: DRF, Django auth, Django ORM.
- Used by: `/api/` routes, cron scripts, tests, and some utility logic.

**Domain Data Layer:**
- Purpose: Persist the league state and community state.
- Location: `pickem/pickem_api/models.py`, `pickem/pickem_homepage/models.py`
- Contains: `GamesAndScores`, `GameWeeks`, `GamePicks`, `Teams`, `userSeasonPoints`, `userStats`, `currentSeason`, `UserProfile`, `SiteBanner`, `MessageBoardPost`, `MessageBoardComment`, `MessageBoardVote`.
- Depends on: Django ORM and `django.contrib.auth.models.User`.
- Used by: UI views, API views, serializers, admin classes, context processors, template filters.

**Scheduled Update Layer:**
- Purpose: Pull ESPN/NFL data and update app state.
- Location: `pickem/pickem_api/cron_update_games_v2.py`, `pickem/pickem_api/cron_update_picks.py`, `pickem/pickem_api/cron_update_standings.py`, `pickem/pickem_api/cron_update_records.py`, `charts/family-pickem/templates/cronjob.yaml`.
- Contains: Standalone Python scripts using `requests` and optional token headers.
- Depends on: ESPN public APIs and this app's `/api/` endpoints.
- Used by: Manual shell execution and Kubernetes CronJob command values.

**Presentation Assets:**
- Purpose: Provide templates, Tailwind output, legacy CSS, images, team logos, and JavaScript snippets.
- Location: `pickem/pickem_homepage/templates/pickem/`, `pickem/pickem_homepage/static/`, `pickem/pickem/static/`
- Contains: `base.html`, page templates, `input.css`, `tailwind.css`, copied image assets.
- Depends on: Django staticfiles and template context processors.
- Used by: Browser page rendering.

**Deployment Layer:**
- Purpose: Package and deploy the Django app and scheduled jobs.
- Location: `docker/`, `charts/family-pickem/`, `infra/`, `.github/workflows/`
- Contains: Dockerfile, Helm chart templates, environment secret references, ArgoCD app manifests, artifact publishing workflows.
- Depends on: Kubernetes, Helm, Docker, GitHub Actions.
- Used by: Release builds and GitOps deployment.

## Data Flow

### Primary Request Path

1. Browser request enters root URL routing (`pickem/pickem/urls.py:19`).
2. Page routes dispatch to `pickem_homepage.views` through `pickem/pickem_homepage/urls.py:8`.
3. View reads and aggregates ORM data from `pickem_api.models` and `pickem_homepage.models` (`pickem/pickem_homepage/views.py:57`, `pickem/pickem_homepage/views.py:292`, `pickem/pickem_homepage/views.py:336`).
4. Global context processors add theme, banner, and footer stats (`pickem/pickem/settings.py:120`, `pickem/pickem/context_processors.py:14`).
5. Templates render from `pickem/pickem_homepage/templates/pickem/`, with `base.html` owning navigation and static asset includes (`pickem/pickem_homepage/templates/pickem/base.html:31`).

### API Request Path

1. API request enters `/api/` in root routing (`pickem/pickem/urls.py:21`).
2. Endpoint routes dispatch through `pickem/pickem_api/urls.py`.
3. Function views parse JSON, query or mutate ORM models, and serialize responses (`pickem/pickem_api/views.py:53`, `pickem/pickem_api/views.py:140`, `pickem/pickem_api/views.py:381`).
4. DRF permissions allow reads and restrict writes to staff for most mutable endpoints through `IsAdminOrReadOnly` (`pickem/pickem_api/permissions.py:4`).
5. Serializers map model fields to response/request payloads (`pickem/pickem_api/serializers.py:24`, `pickem/pickem_api/serializers.py:36`, `pickem/pickem_api/serializers.py:63`).

### Pick Submission Flow

1. `/picks/` loads the current date, resolves week and competition from `GameWeeks`, and queries games and existing picks (`pickem/pickem_homepage/views.py:528`).
2. The page renders `pickem/picks.html` with `GamesAndScores`, `Teams`, `GamePicks`, and auth-required state (`pickem/pickem_homepage/views.py:567`).
3. POST data is validated through `GamePicksForm` and saved as `GamePicks` (`pickem/pickem_homepage/forms.py:7`, `pickem/pickem_homepage/views.py:582`).
4. Edits go through `/picks/edit/`, which verifies ownership and uses `pickem.utils.is_pick_locked` before updating (`pickem/pickem_homepage/views.py:593`, `pickem/pickem/utils.py:54`).

### Scheduled Game Update Flow

1. Kubernetes CronJob runs the configured command from the deployed image (`charts/family-pickem/templates/cronjob.yaml:23`).
2. `cron_update_games_v2.py` fetches the season through `/api/currentseason/` and ESPN scoreboard data (`pickem/pickem_api/cron_update_games_v2.py:60`, `pickem/pickem_api/cron_update_games_v2.py:168`).
3. The script maps ESPN payloads into `GamesAndScores` fields, including betting, weather, venue, broadcast, and Gamecast values (`pickem/pickem_api/cron_update_games_v2.py:287`, `pickem/pickem_api/cron_update_games_v2.py:383`).
4. Existing games are PUT to `/api/games/<id>`; new games are POSTed to `/api/games/` (`pickem/pickem_api/cron_update_games_v2.py:145`).

### Pick Scoring Flow

1. `cron_update_picks.py` reads finished unscored games from `/api/unscored` (`pickem/pickem_api/cron_update_picks.py:128`).
2. For each finished game, it reads matching picks from `/api/picks/<game_id>` (`pickem/pickem_api/cron_update_picks.py:63`).
3. Correct picks are patched through `/api/userpicks/<pick_id>` (`pickem/pickem_api/cron_update_picks.py:74`).
4. The game is marked scored through `/api/games/<game_id>` (`pickem/pickem_api/cron_update_picks.py:90`).
5. `cron_update_standings.py` counts correct picks per user/week and patches `userSeasonPoints` through `/api/userpoints/<season>/<uid>` (`pickem/pickem_api/cron_update_standings.py:188`, `pickem/pickem_api/cron_update_standings.py:154`).

### Community Flow

1. Homepage loads recent active message-board posts and user vote state (`pickem/pickem_homepage/views.py:195`).
2. Authenticated users create posts through `/message-board/create-post/` (`pickem/pickem_homepage/views.py:1211`).
3. Comments and nested replies are created through `/message-board/create-comment/` (`pickem/pickem_homepage/views.py:1256`).
4. Vote endpoints mutate `MessageBoardVote`; model `save()`/`delete()` methods update denormalized counts on posts/comments (`pickem/pickem_homepage/views.py:1320`, `pickem/pickem_homepage/models.py:192`).

**State Management:**
- Persistent state is Django ORM-backed in PostgreSQL through models in `pickem/pickem_api/models.py` and `pickem/pickem_homepage/models.py`.
- User session state is Django auth/session middleware configured in `pickem/pickem/settings.py`.
- Theme state is stored on `UserProfile.dark_mode` and injected globally by `theme_context` (`pickem/pickem/context_processors.py:14`).
- Current season is database-backed in `currentSeason` and read through `pickem.utils.get_season` and API-local `get_season` (`pickem/pickem/utils.py:5`, `pickem/pickem_api/views.py:22`).

## Key Abstractions

**Season Context:**
- Purpose: Resolve the active season for page queries, API queries, cron jobs, and display labels.
- Examples: `pickem/pickem/utils.py`, `pickem/pickem_api/models.py`, `pickem/pickem_api/views.py`, `pickem/pickem_api/cron_update_games_v2.py`.
- Pattern: `currentSeason` model lookup with fallbacks; cron scripts read `/api/currentseason/`.

**Game/Pick Domain:**
- Purpose: Represent NFL games and user predictions.
- Examples: `GamesAndScores`, `GamePicks`, `GameWeeks`, `Teams` in `pickem/pickem_api/models.py`.
- Pattern: Denormalized game and team fields, string/slug identifiers, week and season columns on every relevant record.

**Season Points:**
- Purpose: Store weekly points, bonuses, winners, total points, and rank.
- Examples: `userSeasonPoints` and `userPoints` in `pickem/pickem_api/models.py`.
- Pattern: One row per user/season with fixed `week_1_*` through `week_18_*` fields.

**Commissioner Authorization:**
- Purpose: Gate commissioner dashboard and manual operations.
- Examples: `is_commissioner` and `commissioner_required` in `pickem/pickem_homepage/views.py`.
- Pattern: Allow `UserProfile.is_commissioner` or `User.is_superuser`.

**Read-Open API Permission:**
- Purpose: Let anonymous callers read API data while staff users mutate it.
- Examples: `IsAdminOrReadOnly` in `pickem/pickem_api/permissions.py`.
- Pattern: SAFE_METHODS are public; writes require `request.user.is_staff`.

**Template Filters:**
- Purpose: Keep templates concise for common lookups and computed presentation values.
- Examples: `lookupavatar`, `lookuplogo`, `lookupStats`, `is_game_locked`, `game_lock_reason` in `pickem/pickem_homepage/templatetags/pickem_homepage_extras.py`.
- Pattern: Django `@register.filter` and `@register.simple_tag` functions that query ORM data.

**Site Banner:**
- Purpose: Manage one active site-wide message with scheduling and priority.
- Examples: `SiteBanner.get_active_banner` in `pickem/pickem_homepage/models.py`, `site_banner_context` in `pickem/pickem/context_processors.py`.
- Pattern: Model method selects the active record; context processor injects it into every template.

## Entry Points

**Django CLI:**
- Location: `pickem/manage.py`
- Triggers: `python manage.py ...`
- Responsibilities: Set `DJANGO_SETTINGS_MODULE=pickem.settings` and run Django management commands.

**WSGI App:**
- Location: `pickem/pickem/wsgi.py`
- Triggers: Production WSGI server or Docker entrypoint command.
- Responsibilities: Expose `application = get_wsgi_application()`.

**ASGI App:**
- Location: `pickem/pickem/asgi.py`
- Triggers: ASGI server.
- Responsibilities: Expose `application = get_asgi_application()`.

**Root URLs:**
- Location: `pickem/pickem/urls.py`
- Triggers: All HTTP requests.
- Responsibilities: Mount `pickem_homepage.urls` at `/`, `pickem_api.urls` at `/api/`, and Django admin at `/admin/`.

**Homepage URLs:**
- Location: `pickem/pickem_homepage/urls.py`
- Triggers: Browser page and AJAX routes.
- Responsibilities: Route home, scores, standings, rules, picks, profile, message board, commissioner, allauth, and logout endpoints.

**API URLs:**
- Location: `pickem/pickem_api/urls.py`
- Triggers: REST clients and cron scripts.
- Responsibilities: Route current season, games, weeks, picks, teams, active games, unscored games, and user point endpoints.

**Scheduled Scripts:**
- Location: `pickem/pickem_api/cron_update_games_v2.py`, `pickem/pickem_api/cron_update_picks.py`, `pickem/pickem_api/cron_update_standings.py`, `pickem/pickem_api/cron_update_records.py`
- Triggers: Shell, cron, Kubernetes CronJob.
- Responsibilities: Fetch external data, update scores, score picks, standings, and team records through HTTP APIs.

**Management Commands:**
- Location: `pickem/pickem_homepage/management/commands/createsu.py`, `pickem/pickem_homepage/management/commands/manage_banners.py`
- Triggers: `python manage.py createsu`, `python manage.py manage_banners`.
- Responsibilities: Create an admin user and manage site banners.

## Architectural Constraints

- **Threading:** Django request/response execution is synchronous function-based view code. Cron scripts are synchronous Python processes using `requests`.
- **Global state:** `pickem/pickem/settings.py` reads environment variables at import time; cron scripts parse `argparse` at module import time in `pickem/pickem_api/cron_*.py`; `pickem/pickem_homepage/views.py` contains module-level helper functions and imported models.
- **Circular imports:** The utility layer imports `currentSeason` from `pickem_api.models` (`pickem/pickem/utils.py:3`), while homepage views and template tags import `pickem.utils`; avoid adding model imports back from `pickem_api.models` into `pickem.utils`.
- **Authentication:** Page auth uses Django decorators and allauth routes; API auth uses SessionAuthentication and TokenAuthentication in `pickem/pickem/settings.py`.
- **Mutable API endpoints:** API writes depend on staff authentication via `IsAdminOrReadOnly`, so cron clients need valid token/session credentials when writes are protected.
- **Static output:** Tailwind output is committed/generated at `pickem/pickem_homepage/static/css/tailwind.css`; source tokens/classes live in `pickem/pickem_homepage/static/css/input.css` and templates.
- **Database coupling:** Many records use denormalized user IDs/emails and string week fields; update code must keep `userEmail`, `userID`, `uid`, `gameseason`, `gameWeek`, and `competition` aligned.

## Anti-Patterns

### Adding New Page Logic To API Views

**What happens:** Browser-oriented aggregation, templates, messages, and form handling are placed in API modules.
**Why it's wrong:** `pickem_api.views` is consumed by cron scripts and external JSON clients; mixing templates into it makes endpoints harder to serialize and secure.
**Do this instead:** Put browser routes in `pickem/pickem_homepage/views.py` and expose only JSON access in `pickem/pickem_api/views.py`.

### Directly Bypassing Pick Lock Helpers

**What happens:** Code updates `GamePicks` without calling the shared lock rules.
**Why it's wrong:** Pick edit rules depend on Sunday 1 PM Eastern and game status logic in `pickem/pickem/utils.py`.
**Do this instead:** Use `is_pick_locked` or `are_picks_locked_for_week` from `pickem/pickem/utils.py`, as `edit_game_pick` does in `pickem/pickem_homepage/views.py`.

### Hardcoding Season Values In Views

**What happens:** Query code uses a literal season instead of resolving `currentSeason`.
**Why it's wrong:** Page, API, and cron flows depend on the configured database season.
**Do this instead:** Use `get_season()` from `pickem/pickem/utils.py` in page code and `/api/currentseason/` in standalone scripts.

### Creating New League Data Models In Homepage App

**What happens:** Game, pick, team, season, or stats tables are added under `pickem_homepage.models`.
**Why it's wrong:** API serializers, cron scripts, and admin registration expect league domain models in `pickem_api.models`.
**Do this instead:** Add league data models to `pickem/pickem_api/models.py`; reserve `pickem/pickem_homepage/models.py` for UI/community/site content such as banners and message board.

## Error Handling

**Strategy:** Views and scripts use localized `try`/`except` blocks with JSON error responses, redirects/messages, or printed/logged script output.

**Patterns:**
- API views return `JsonResponse` with explicit HTTP statuses for not found, bad request, and validation errors (`pickem/pickem_api/views.py:92`, `pickem/pickem_api/views.py:159`).
- Homepage AJAX endpoints return JSON envelopes such as `{'success': False, 'error': ...}` (`pickem/pickem_homepage/views.py:1138`, `pickem/pickem_homepage/views.py:1256`).
- Page flows use Django `messages` plus redirects for commissioner and profile workflows (`pickem/pickem_homepage/views.py:43`, `pickem/pickem_homepage/views.py:702`).
- Context processors catch broad exceptions and return safe defaults so templates render during migrations or database issues (`pickem/pickem/context_processors.py:54`, `pickem/pickem/context_processors.py:72`).
- Cron scripts print or log HTTP/API failures and continue through procedural update functions (`pickem/pickem_api/cron_update_picks.py:15`, `pickem/pickem_api/cron_update_games_v2.py:428`).

## Cross-Cutting Concerns

**Logging:** Cron scripts use `print` and, in `cron_update_picks.py`, root `logging`; web views mostly rely on responses and Django messages.
**Validation:** Forms validate submitted page data in `pickem/pickem_homepage/forms.py`; DRF serializers validate API payloads in `pickem/pickem_api/serializers.py`; some AJAX endpoints validate inline in `pickem/pickem_homepage/views.py`.
**Authentication:** Google OAuth routes are included through allauth in `pickem/pickem_homepage/urls.py`; settings configure allauth in `pickem/pickem/settings.py`; API auth is DRF session/token auth.
**Authorization:** Commissioner pages use `commissioner_required`; API mutations use `IsAdminOrReadOnly` or `IsAdminUser`.
**Theme:** Dark mode is stored on `UserProfile.dark_mode`, injected through `theme_context`, and applied as a class on `<html>` in `base.html`.
**Static Assets:** Use `{% static %}` paths in templates; keep Tailwind input/output in `pickem/pickem_homepage/static/css/`.
**External Data:** ESPN data ingestion belongs in the cron scripts under `pickem/pickem_api/`; do not add external API calls inside templates.

---

*Architecture analysis: 2026-06-28*
