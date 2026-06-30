# Testing Patterns

**Analysis Date:** 2026-06-28

## Test Framework

**Runner:**
- Django test runner from Django 4.0.2, invoked through `pickem/manage.py`.
- Test classes subclass `django.test.TestCase` in `pickem/pickem_api/tests.py` and `pickem/pickem_homepage/tests.py`.
- Config: no `pytest.ini`, `tox.ini`, `setup.cfg`, `pyproject.toml`, `jest.config.*`, or `vitest.config.*` is detected.
- Test-specific Django settings are available in `pickem/pickem/test_settings.py`.

**Assertion Library:**
- Python `unittest` assertions inherited from `django.test.TestCase`: `assertEqual`, `assertTrue`, `assertFalse`, `assertIsNone`, `assertIsNotNone`, `assertIsInstance`, `assertIn`, and `assertNotIn`.
- DRF serializers are tested by instantiating serializer classes from `pickem/pickem_api/serializers.py` and asserting on `serializer.data`.

**Run Commands:**
```bash
cd pickem && python manage.py test              # Run all Django tests using default settings
cd pickem && python manage.py test --settings=pickem.test_settings              # Run all tests with in-memory SQLite test settings
cd pickem && python manage.py test pickem_api pickem_homepage --settings=pickem.test_settings              # Run app test suites with test settings
```

## Test File Organization

**Location:**
- Tests are app-level and use Django's default `tests.py` discovery pattern.
- Core API/model/serializer tests live in `pickem/pickem_api/tests.py`.
- Homepage, utility, message board, banner, and system-check tests live in `pickem/pickem_homepage/tests.py`.
- Test settings live in `pickem/pickem/test_settings.py`.

**Naming:**
- Test files use Django default names: `tests.py`.
- Test case classes end with `Test` or `Tests`: `UserProfileModelTest`, `GameSerializerTest`, `ViewSmokeTests`, `IsCommissionerTests`, and `DjangoSystemCheckTests`.
- Test methods use `test_<expected_behavior>` names: `test_create_profile`, `test_valid_data`, `test_scores_returns_200`, `test_returns_default_int_when_no_record`, and `test_is_currently_active_false_after_end`.

**Structure:**
```text
pickem/
├── pickem/
│   └── test_settings.py
├── pickem_api/
│   └── tests.py
└── pickem_homepage/
    └── tests.py
```

## Test Structure

**Suite Organization:**
```python
from django.test import TestCase
from django.contrib.auth.models import User

from pickem_api.models import UserProfile


class UserProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_create_profile(self):
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(profile.user, self.user)
```

**Patterns:**
- Group tests by model, serializer, helper, or page family. Examples: `TeamsModelTest`, `GamePicksSerializerTest`, `IsCommissionerTests`, and `SiteBannerModelTests`.
- Use `setUp()` for per-test objects that may be mutated, as in `UserProfileModelTest` in `pickem/pickem_api/tests.py`.
- Use `setUpTestData()` for shared immutable database setup, especially users, `Site`, and `currentSeason` records in `pickem/pickem_homepage/tests.py`.
- Use Django `Client` for route smoke tests in `ViewSmokeTests` in `pickem/pickem_homepage/tests.py`.
- Use `call_command("check")` to verify Django system checks in `DjangoSystemCheckTests` in `pickem/pickem_homepage/tests.py`.
- Assert HTTP status codes directly for smoke coverage of public and auth-required pages: 200 for anonymous public routes and 302 for auth-required routes in `pickem/pickem_homepage/tests.py`.

## Mocking

**Framework:** Not detected. No `unittest.mock.patch`, pytest monkeypatching, or third-party mocking library usage is present in project tests.

**Patterns:**
```python
class GetSeasonTests(TestCase):
    def test_returns_default_int_when_no_record(self):
        currentSeason.objects.all().delete()
        result = get_season()
        self.assertEqual(result, 2024)
```

**What to Mock:**
- Mock external HTTP calls from cron scripts and template filters when adding tests for `pickem/pickem_api/cron_update_games_v2.py`, `pickem/pickem_api/cron_update_picks.py`, `pickem/pickem_api/cron_update_standings.py`, and `lookupavatar()` in `pickem/pickem_homepage/templatetags/pickem_homepage_extras.py`.
- Mock browser/global APIs only if JavaScript tests are introduced for `pickem/pickem_homepage/static/css/dark-mode.js`; no JavaScript test runner exists now.

**What NOT to Mock:**
- Do not mock Django ORM models for model methods, serializer output, utility functions, or route smoke tests. Existing tests create real test database rows in `pickem/pickem_api/tests.py` and `pickem/pickem_homepage/tests.py`.
- Do not mock `is_commissioner()` dependencies when the behavior can be tested with real `User` and `UserProfile` rows, as shown in `IsCommissionerTests`.

## Fixtures and Factories

**Test Data:**
```python
@classmethod
def setUpTestData(cls):
    Site.objects.get_or_create(
        id=1, defaults={"domain": "testserver", "name": "testserver"}
    )
    currentSeason.objects.create(season=2526, display_name="2025-2026")
```

**Location:**
- No dedicated fixture files, factory classes, factory_boy setup, or JSON fixtures are detected.
- Inline ORM setup is the project pattern. Use `User.objects.create_user()`, `User.objects.create_superuser()`, `currentSeason.objects.create()`, and model-specific `objects.create()` calls in test methods or `setUpTestData()`.
- Use deterministic season data in tests, currently `season=2526` and `display_name="2025-2026"` in `pickem/pickem_homepage/tests.py` and `pickem/pickem_api/tests.py`.
- Use minimal required model fields. For example, `GamesAndScoresModelTest` in `pickem/pickem_api/tests.py` creates a game with required team, status, and timestamp fields only.

## Coverage

**Requirements:** None enforced. No `.coveragerc`, `coverage` dependency, CI coverage gate, or coverage command is detected.

**View Coverage:**
```bash
# Not configured in repository
```

## Test Types

**Unit Tests:**
- Model defaults and string methods are tested in `pickem/pickem_api/tests.py` for `UserProfile`, `Teams`, `GamesAndScores`, `GamePicks`, `userSeasonPoints`, `GameWeeks`, `userStats`, and `currentSeason`.
- Serializer output is tested in `pickem/pickem_api/tests.py` for `GameSerializer`, `currentSeasonSerializer`, `TeamsSerializer`, and `GamePicksSerializer`.
- Utility/helper behavior is tested in `pickem/pickem_homepage/tests.py` for `is_commissioner()` and `pickem.utils.get_season()`.
- Message board and banner model behavior is tested in `pickem/pickem_homepage/tests.py` for `MessageBoardPost`, `MessageBoardComment`, and `SiteBanner`.

**Integration Tests:**
- Route smoke tests in `ViewSmokeTests` exercise Django URL routing, template rendering, context processors, and app setup for `/`, `/scores/`, `/standings/`, `/rules/`, `/picks/`, `/profile/`, `/commissioners/`, `/api/currentseason`, `/api/games`, and `/api/weeks`.
- `DjangoSystemCheckTests` runs Django's system checks through `call_command("check")`.

**E2E Tests:**
- Not used. No Selenium, Playwright, Cypress, or browser automation test setup is detected.

## Common Patterns

**Async Testing:**
```python
# Not used. Project tests are synchronous Django TestCase tests.
```

**Error Testing:**
```python
def test_authenticated_user_no_profile_returns_false(self):
    user = User.objects.create_user("noprofile", password="pass")
    UserProfile.objects.filter(user=user).delete()
    self.assertFalse(is_commissioner(user))
```

Use state setup to trigger fallback/error branches, then assert the returned status, boolean, or default value. Existing examples include deleting `currentSeason` rows in `GetSeasonTests`, deleting `UserProfile` rows in `IsCommissionerTests`, and testing inactive/future/expired banners in `SiteBannerModelTests`.

---

*Testing analysis: 2026-06-28*
