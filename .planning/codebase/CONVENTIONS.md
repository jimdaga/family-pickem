# Coding Conventions

**Analysis Date:** 2026-06-28

## Naming Patterns

**Files:**
- Use Django app-standard module names for backend code: `models.py`, `views.py`, `forms.py`, `serializers.py`, `admin.py`, `urls.py`, and `tests.py` in `pickem/pickem_api/` and `pickem/pickem_homepage/`.
- Use `cron_<verb>_<domain>.py` for standalone data-update scripts in `pickem/pickem_api/`, such as `pickem/pickem_api/cron_update_games_v2.py`, `pickem/pickem_api/cron_update_picks.py`, and `pickem/pickem_api/cron_update_standings.py`.
- Use Django template names that match route concepts under `pickem/pickem_homepage/templates/pickem/`, such as `home.html`, `picks.html`, `scores.html`, `standings.html`, and `profile.html`.
- Use generated/static CSS names by role: Tailwind source is `pickem/pickem_homepage/static/css/input.css`, compiled output is `pickem/pickem_homepage/static/css/tailwind.css`, and legacy files remain in `pickem/pickem_homepage/static/css/style.css` and `pickem/pickem_homepage/static/css/dark-mode.css`.
- Avoid using `views_temp.py` as a pattern for new code. `pickem/pickem_homepage/views_temp.py` is a temporary/legacy duplicate-style module; put active view code in `pickem/pickem_homepage/views.py`.

**Functions:**
- Use `snake_case` for Python functions and view functions: `is_commissioner()` and `commissioner_required()` in `pickem/pickem_homepage/views.py`, `get_season()` in `pickem/pickem/utils.py`, and `get_current_season_api()` in `pickem/pickem_api/views.py`.
- Use imperative verb phrases for cron helpers: `get_api_headers()`, `get_matching_picks()`, `post_win()`, `update_game_as_scored()`, and `update_picks()` in `pickem/pickem_api/cron_update_picks.py`.
- Use `test_<behavior>` for test methods in `pickem/pickem_api/tests.py` and `pickem/pickem_homepage/tests.py`, for example `test_create_profile`, `test_api_games_returns_200`, and `test_is_currently_active_false_after_end`.
- Use JavaScript `camelCase` methods inside classes, as in `getUserPreference()`, `applyTheme()`, `saveToBackend()`, and `updateToggleUI()` in `pickem/pickem_homepage/static/css/dark-mode.js`.

**Variables:**
- Use `snake_case` for local Python variables: `current_week`, `current_competition`, `season_winner`, `top_players`, and `message_posts` in `pickem/pickem_homepage/views.py`.
- Preserve existing database field names on legacy models even when they are camelCase, such as `teamNameSlug`, `gameWeek`, `startTimestamp`, `homeTeamName`, `tieBreakerScore`, and `pick_correct` in `pickem/pickem_api/models.py`.
- Use explicit context dictionary keys for templates and keep names aligned with template use, as in the `context` dictionary built by `index()` in `pickem/pickem_homepage/views.py`.
- Use uppercase class constants for JavaScript enum-like objects, as in `this.themes = { LIGHT: 'light', DARK: 'dark' }` in `pickem/pickem_homepage/static/css/dark-mode.js`.

**Types:**
- Use `CamelCase` for Django model classes, forms, serializers, admin classes, and test case classes: `UserProfile`, `GamesAndScores`, `MessageBoardPost`, `SiteBannerForm`, `GameSerializer`, `UserProfileAdmin`, and `ViewSmokeTests`.
- Preserve legacy lowercase model class names where the database/API already depends on them: `userSeasonPoints`, `userPoints`, `userStats`, and `currentSeason` in `pickem/pickem_api/models.py`.
- Use `ModelSerializer` classes ending in `Serializer` in `pickem/pickem_api/serializers.py`.
- Use `ModelForm` or `Form` classes ending in `Form` in `pickem/pickem_homepage/forms.py`.

## Code Style

**Formatting:**
- No repository-level formatter configuration is detected. `autopep8==2.0.2` and `pycodestyle==2.11.0` are present in `pickem/requirements.txt`, so use PEP 8-compatible formatting for Python and run autopep8 manually when needed.
- Use 4-space indentation for Python in `pickem/pickem_api/`, `pickem/pickem_homepage/`, and `pickem/pickem/`.
- Use 2-space indentation for JavaScript config and Tailwind config, matching `tailwind.config.js`.
- Keep Django `Meta` classes inside models, forms, and serializers. Examples: `UserProfile.Meta` and `GamesAndScores.Meta` in `pickem/pickem_api/models.py`, `MessageBoardPostForm.Meta` in `pickem/pickem_homepage/forms.py`, and `GamePicksSerializer.Meta` in `pickem/pickem_api/serializers.py`.
- Prefer multi-line tuples/lists/dicts for long Django configuration values such as form `fields` in `pickem/pickem_homepage/forms.py`, admin `list_display` values in `pickem/pickem_api/admin.py`, and settings `INSTALLED_APPS` in `pickem/pickem/settings.py`.

**Linting:**
- No `.flake8`, `setup.cfg`, `pyproject.toml`, `.eslintrc`, `eslint.config.*`, `biome.json`, or `.prettierrc` config is detected.
- `pickem/pickem/test_settings.py` uses `# noqa: F401, F403` for the wildcard test settings import, so use targeted inline suppressions only when a Django settings pattern requires it.
- `package.json` has no JavaScript lint command. Front-end checks are limited to Tailwind build commands: `npm run build:css` and `npm run build:prod`.

## Import Organization

**Order:**
1. Python standard library imports first, such as `from datetime import date`, `import json`, and `from functools import wraps` in `pickem/pickem_homepage/views.py`.
2. Django and third-party framework imports next, such as `django.http`, `django.shortcuts`, `django.db.models`, `rest_framework.*`, and `allauth.*` in `pickem/pickem_api/views.py` and `pickem/pickem_homepage/templatetags/pickem_homepage_extras.py`.
3. Project imports last, such as `from pickem_api.models import ...`, `from pickem.utils import get_season`, and relative imports like `from .forms import ...` in `pickem/pickem_homepage/views.py`.

**Path Aliases:**
- No Python path alias system is configured. Use Django app imports such as `from pickem_api.models import GamesAndScores` and `from pickem_homepage.models import MessageBoardPost`.
- Use relative imports for same-app modules: `from .models import MessageBoardPost` in `pickem/pickem_homepage/forms.py` and `from .serializers import GameSerializer` in `pickem/pickem_api/views.py`.
- No JavaScript module bundler aliases are detected. Browser JavaScript in `pickem/pickem_homepage/static/css/dark-mode.js` uses global DOM APIs directly.

## Error Handling

**Patterns:**
- For expected missing database rows in views, catch specific Django exceptions and return a fallback or `JsonResponse`. Examples: `currentSeason.DoesNotExist` in `pickem/pickem_api/views.py`, `GameWeeks.DoesNotExist` in `pickem/pickem_homepage/views.py`, and `SocialAccount.DoesNotExist` in `pickem/pickem_homepage/templatetags/pickem_homepage_extras.py`.
- For authorization, centralize commissioner checks in `is_commissioner()` and `commissioner_required()` in `pickem/pickem_homepage/views.py`; use `messages.error()` and `redirect('/')` for denied HTML views.
- For API validation, use DRF serializers and return serializer errors with HTTP 400, as in `game_list()` and `game_detail()` in `pickem/pickem_api/views.py`.
- For test-friendly season fallback, use `get_season()` in `pickem/pickem/utils.py`, which returns a configured season or a default when no `currentSeason` row exists.
- Avoid adding new bare `except:` blocks. Existing broad catches in `pickem/pickem_homepage/views.py` are legacy compatibility patterns; prefer explicit exceptions such as `DoesNotExist`, `ValueError`, `TypeError`, and `requests.exceptions.RequestException`.
- In cron scripts, catch network failures around external calls and log or print fallback behavior. `get_season()` in `pickem/pickem_api/cron_update_picks.py` catches `requests.exceptions.RequestException` and computes a season fallback.

## Logging

**Framework:** Python `logging` for cron scripts; Django messages framework for user-facing HTML views; browser `console.warn` for front-end theme persistence failures.

**Patterns:**
- Use module-level or script-level loggers in cron scripts. `pickem/pickem_api/cron_update_picks.py` configures `logger`, `StreamHandler`, and a timestamped `Formatter`.
- Use `logger.info()`, `logger.warning()`, and `logger.error()` in cron jobs for scheduled update outcomes, as in `pickem/pickem_api/cron_update_picks.py`.
- Use `messages.error()` for permission and authentication feedback in HTML views, as in `commissioner_required()` in `pickem/pickem_homepage/views.py`.
- Use `console.warn()` for non-fatal browser-side persistence issues, as in `saveToBackend()` and `setTheme()` in `pickem/pickem_homepage/static/css/dark-mode.js`.
- Avoid `print()` in new web request paths. Some cron scripts and legacy API branches still use `print()`; prefer `logging` in new standalone scripts and Django/DRF responses in request handlers.

## Comments

**When to Comment:**
- Use comments to explain domain rules, fallback behavior, or non-obvious compatibility requirements. Good examples include season fallback comments in `pickem/pickem_api/cron_update_picks.py`, pick-locking rule comments in `pickem/pickem/utils.py`, and banner priority comments in `pickem/pickem_homepage/models.py`.
- Keep comments close to the code they explain. Examples include "Get current week information" and "Build a lookup of user ID -> overall season rank" in `pickem/pickem_homepage/views.py`.
- Avoid comments that only repeat the statement that follows. Legacy comments like "Create your models here" in `pickem/pickem_api/models.py` should not be copied into new code.

**JSDoc/TSDoc:**
- JavaScript uses block comments above class methods instead of generated API docs. Follow the `DarkModeManager` style in `pickem/pickem_homepage/static/css/dark-mode.js` for non-trivial browser helpers.
- Python uses docstrings on models, helpers, forms, template filters, tests, and cron helpers. Examples: `SiteBanner` in `pickem/pickem_homepage/models.py`, `QuickCommentForm.clean_content()` in `pickem/pickem_homepage/forms.py`, and `GetSeasonTests` in `pickem/pickem_homepage/tests.py`.

## Function Design

**Size:** Keep new functions focused and testable. Existing large view functions such as `index()` in `pickem/pickem_homepage/views.py` are legacy accumulation points; extract new reusable behavior into helpers in `pickem/pickem/utils.py`, form methods in `pickem/pickem_homepage/forms.py`, model properties/methods in `pickem/pickem_homepage/models.py`, or small private helpers near the view.

**Parameters:** Prefer explicit parameters and Django objects over implicit globals. Good examples include `is_pick_locked(game, week_games=None)` and `are_picks_locked_for_week(week_games)` in `pickem/pickem/utils.py`. Cron scripts currently rely on parsed module-level `args`; keep that pattern only inside standalone scripts such as `pickem/pickem_api/cron_update_picks.py`.

**Return Values:** Return Django `HttpResponse`/`JsonResponse`/DRF `Response` from views, dictionaries for template context helper data, tuples for compact rule checks such as `(is_locked, reason)` in `pickem/pickem/utils.py`, and model/queryset objects from template filters only when templates already expect them.

## Module Design

**Exports:** Django modules expose functions/classes by convention rather than explicit `__all__`. Put app-specific models in `pickem/pickem_api/models.py` or `pickem/pickem_homepage/models.py`, serializers in `pickem/pickem_api/serializers.py`, forms in `pickem/pickem_homepage/forms.py`, and template filters in `pickem/pickem_homepage/templatetags/pickem_homepage_extras.py`.

**Barrel Files:** Barrel files are not used. `__init__.py` files in `pickem/pickem_api/`, `pickem/pickem_homepage/`, and `pickem/pickem/` are package markers; import directly from the concrete module path.

---

*Convention analysis: 2026-06-28*
