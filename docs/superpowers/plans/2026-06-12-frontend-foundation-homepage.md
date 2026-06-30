# Frontend Foundation and Homepage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared Broadcast Blue light/dark design foundation and replace the homepage with the approved compact NFL weekly dashboard.

**Architecture:** Keep Django templates and Tailwind CSS, but move repeated shell and dashboard structures into focused includes. Build a template-ready homepage dashboard in Python so templates render data rather than calculating ranks and pick states. Shared navigation, banner dismissal, menu behavior, and theme switching move from inline scripts into one static JavaScript file.

**Tech Stack:** Django 4.0 templates and TestCase, Python 3.10, Tailwind CSS 3.4, vanilla JavaScript, Docker Compose, Codex in-app browser.

---

## Scope and Working-Tree Rules

This is the first implementation slice from the approved design spec. It delivers a working shared shell and homepage; picks, scores, standings, profiles, rules, settings, and commissioner page migrations receive separate follow-up plans.

The branch already contains user-authored, uncommitted changes in:

```text
pickem/pickem_api/cron_update_records.py
pickem/pickem_homepage/static/css/tailwind.css
pickem/pickem_homepage/templates/pickem/home.html
pickem/pickem_homepage/views.py
```

Rules for execution:

- Do not modify or stage `pickem/pickem_api/cron_update_records.py`.
- Preserve the week-points behavior currently added to `home.html` and `views.py`; integrate it into the compact standings/dashboard presentation.
- Treat `static/css/tailwind.css` as generated output. Regenerate it after editing `input.css` or templates.
- Do not add `.superpowers/` or `AGENTS.md` to implementation commits.
- Before every commit, stage explicit file paths and inspect `git diff --cached --stat`.

## File Map

### Create

```text
pickem/pickem_homepage/homepage_dashboard.py
pickem/pickem_homepage/test_homepage_redesign.py
pickem/pickem_homepage/static/js/site-shell.js
pickem/pickem_homepage/static/js/home-message-board.js
pickem/pickem_homepage/templates/pickem/components/primary_nav.html
pickem/pickem_homepage/templates/pickem/components/mobile_nav.html
pickem/pickem_homepage/templates/pickem/components/site_banner.html
pickem/pickem_homepage/templates/pickem/components/module_header.html
pickem/pickem_homepage/templates/pickem/components/status_label.html
pickem/pickem_homepage/templates/pickem/components/home_pick_status.html
pickem/pickem_homepage/templates/pickem/components/home_game_row.html
pickem/pickem_homepage/templates/pickem/components/home_season_summary.html
pickem/pickem_homepage/templates/pickem/components/home_standings.html
pickem/pickem_homepage/templates/pickem/components/home_activity.html
pickem/pickem_homepage/templates/pickem/components/home_message_board.html
```

### Modify

```text
tailwind.config.js
pickem/pickem_homepage/static/css/input.css
pickem/pickem_homepage/static/css/tailwind.css
pickem/pickem_homepage/templates/pickem/base.html
pickem/pickem_homepage/templates/pickem/home.html
pickem/pickem_homepage/views.py
```

## Task 1: Characterize Existing Homepage Behavior

**Files:**
- Create: `pickem/pickem_homepage/test_homepage_redesign.py`
- Read only: `pickem/pickem_homepage/views.py`
- Read only: `pickem/pickem_homepage/templates/pickem/home.html`

- [ ] **Step 1: Add shared homepage test data helpers**

Create `pickem/pickem_homepage/test_homepage_redesign.py`:

```python
from datetime import date

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import TestCase
from django.utils import timezone

from pickem_api.models import (
    GamePicks,
    GamesAndScores,
    GameWeeks,
    currentSeason,
    userSeasonPoints,
)


class HomepageRedesignTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1,
            defaults={"domain": "testserver", "name": "testserver"},
        )
        currentSeason.objects.create(
            season=2526,
            display_name="2025-2026",
        )
        GameWeeks.objects.create(
            weekNumber=1,
            competition="nfl",
            date=date.today(),
            season=2526,
        )
        cls.user = User.objects.create_user(
            username="jim",
            email="jim@example.com",
            password="pass",
        )
        cls.other_user = User.objects.create_user(
            username="mike",
            email="mike@example.com",
            password="pass",
        )
        cls.game = GamesAndScores.objects.create(
            id=1001,
            slug="bills-jets-2526-1",
            competition="nfl",
            gameseason=2526,
            gameWeek="1",
            gameyear="2025",
            startTimestamp=timezone.now(),
            statusType="notstarted",
            statusTitle="Thu 8:15 PM",
            homeTeamId=1,
            homeTeamSlug="jets",
            homeTeamName="New York Jets",
            awayTeamId=2,
            awayTeamSlug="bills",
            awayTeamName="Buffalo Bills",
        )
        userSeasonPoints.objects.create(
            userID=str(cls.user.id),
            userEmail=cls.user.email,
            gameseason=2526,
            total_points=38,
        )
        userSeasonPoints.objects.create(
            userID=str(cls.other_user.id),
            userEmail=cls.other_user.email,
            gameseason=2526,
            total_points=36,
        )
```

- [ ] **Step 2: Add characterization tests for current custom homepage data**

Append:

```python
class HomepageExistingBehaviorTests(HomepageRedesignTestCase):
    def test_week_points_include_users_with_correct_picks(self):
        GamePicks.objects.create(
            id="jim-pick-1",
            pick_game_id=self.game.id,
            slug=self.game.slug,
            uid=self.user.id,
            userID=str(self.user.id),
            userEmail=self.user.email,
            gameseason=2526,
            gameWeek="1",
            gameyear="2025",
            competition="nfl",
            pick="bills",
            pick_correct=True,
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_week_points"])
        self.assertEqual(
            list(response.context["week_points"]),
            [{"uid": self.user.id, "wins": 1}],
        )

    def test_authenticated_pick_progress_uses_current_week_games(self):
        self.client.force_login(self.user)

        response = self.client.get("/")

        self.assertEqual(response.context["current_games"], 1)
        self.assertEqual(response.context["user_picks_count"], 0)
        self.assertEqual(response.context["user_pick_status"], "pending")

    def test_homepage_preserves_message_board_context(self):
        response = self.client.get("/")

        self.assertIn("message_posts", response.context)
        self.assertIn("post_form", response.context)
        self.assertIn("user_rankings", response.context)
```

- [ ] **Step 3: Run the characterization tests**

Run from `pickem/`:

```bash
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.HomepageExistingBehaviorTests -v 2
```

Expected: PASS. These are characterization tests for the user-authored uncommitted work, so they establish the behavior that the redesign must preserve.

- [ ] **Step 4: Commit only the characterization tests**

```bash
git add pickem/pickem_homepage/test_homepage_redesign.py
git diff --cached --stat
git commit -m "test: characterize homepage dashboard data"
```

Expected staged files: only `pickem/pickem_homepage/test_homepage_redesign.py`.

## Task 2: Establish Broadcast Blue Semantic Tokens

**Files:**
- Modify: `tailwind.config.js:8-42`
- Modify: `pickem/pickem_homepage/static/css/input.css:1-90`
- Modify generated: `pickem/pickem_homepage/static/css/tailwind.css`
- Test: `pickem/pickem_homepage/test_homepage_redesign.py`

- [ ] **Step 1: Write failing token and CSS contract tests**

Append:

```python
from pathlib import Path

from django.conf import settings


class FrontendTokenContractTests(TestCase):
    def read_project_file(self, relative_path):
        project_root = Path(settings.BASE_DIR).parent
        return (project_root / relative_path).read_text()

    def test_tailwind_config_defines_broadcast_blue_semantic_tokens(self):
        config = self.read_project_file("tailwind.config.js")

        self.assertIn("'canvas-light': '#EDF0F3'", config)
        self.assertIn("'canvas-dark': '#171B20'", config)
        self.assertIn("'accent-light': '#2563A6'", config)
        self.assertIn("'accent-dark': '#4F91D9'", config)
        self.assertIn("sans: ['Inter', 'system-ui', 'sans-serif']", config)
        self.assertNotIn("'Urbanist'", config)

    def test_shared_css_defines_compact_module_and_button_contracts(self):
        css = self.read_project_file(
            "pickem/pickem_homepage/static/css/input.css"
        )

        self.assertIn(".app-module", css)
        self.assertIn(".app-module-header", css)
        self.assertIn(".app-button-primary", css)
        self.assertIn(".app-status", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
```

- [ ] **Step 2: Run the contract tests and verify RED**

```bash
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.FrontendTokenContractTests -v 2
```

Expected: FAIL because the semantic tokens and compact component classes do not exist.

- [ ] **Step 3: Replace the Tailwind design tokens**

Replace `theme.extend` in `tailwind.config.js` with:

```javascript
extend: {
  colors: {
    'canvas-light': '#EDF0F3',
    'canvas-dark': '#171B20',
    'surface-light': '#FFFFFF',
    'surface-dark': '#252B32',
    'surface-subtle-light': '#F6F7F8',
    'surface-subtle-dark': '#20262C',
    'nav-light': '#141920',
    'nav-dark': '#0E1115',
    'border-light': '#D7DCE1',
    'border-dark': '#39414A',
    'text-light': '#1B2028',
    'text-dark': '#EDF1F5',
    'muted-light': '#6D747D',
    'muted-dark': '#969FA9',
    'accent-light': '#2563A6',
    'accent-dark': '#4F91D9',
    'accent-hover-light': '#1F548D',
    'accent-hover-dark': '#6FA9E8',
    'positive-light': '#2E7D57',
    'positive-dark': '#56B887',
    'negative-light': '#B84242',
    'negative-dark': '#E07171',
    'warning-light': '#9B6B13',
    'warning-dark': '#D1A94D',
  },
  fontFamily: {
    sans: ['Inter', 'system-ui', 'sans-serif'],
    mono: ['ui-monospace', 'monospace'],
  },
  borderRadius: {
    panel: '0.375rem',
    control: '0.25rem',
  },
},
```

Keep `darkMode`, `content`, and `plugins` unchanged.

- [ ] **Step 4: Replace the first shared component layer**

Replace the generic card, button, navigation, banner, and form definitions at the top of `input.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html {
    @apply bg-canvas-light font-sans text-text-light antialiased;
  }

  html.dark {
    @apply bg-canvas-dark text-text-dark;
    color-scheme: dark;
  }

  body {
    @apply min-h-screen bg-canvas-light text-text-light;
  }

  .dark body {
    @apply bg-canvas-dark text-text-dark;
  }

  :focus-visible {
    @apply outline-none ring-2 ring-accent-light ring-offset-2 ring-offset-canvas-light;
  }

  .dark :focus-visible {
    @apply ring-accent-dark ring-offset-canvas-dark;
  }
}

@layer components {
  .app-page {
    @apply mx-auto w-full max-w-7xl px-4 py-5 sm:px-6 lg:py-6;
  }

  .app-module {
    @apply overflow-hidden rounded-panel border border-border-light bg-surface-light;
  }

  .dark .app-module {
    @apply border-border-dark bg-surface-dark;
  }

  .app-module-header {
    @apply flex min-h-10 items-center justify-between gap-3 border-b border-border-light px-3 py-2;
  }

  .dark .app-module-header {
    @apply border-border-dark;
  }

  .app-module-title {
    @apply text-xs font-bold uppercase tracking-wide text-text-light;
  }

  .dark .app-module-title {
    @apply text-text-dark;
  }

  .app-link {
    @apply text-sm font-semibold text-accent-light hover:text-accent-hover-light;
  }

  .dark .app-link {
    @apply text-accent-dark hover:text-accent-hover-dark;
  }

  .app-button-primary {
    @apply inline-flex min-h-11 items-center justify-center rounded-control bg-accent-light px-4 py-2 text-sm font-bold text-white hover:bg-accent-hover-light disabled:cursor-not-allowed disabled:opacity-50;
  }

  .dark .app-button-primary {
    @apply bg-accent-dark text-nav-dark hover:bg-accent-hover-dark;
  }

  .app-button-secondary {
    @apply inline-flex min-h-11 items-center justify-center rounded-control border border-border-light bg-surface-light px-4 py-2 text-sm font-semibold text-text-light hover:bg-surface-subtle-light;
  }

  .dark .app-button-secondary {
    @apply border-border-dark bg-surface-dark text-text-dark hover:bg-surface-subtle-dark;
  }

  .app-status {
    @apply inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide;
  }

  .app-status-live,
  .app-status-success {
    @apply text-positive-light;
  }

  .dark .app-status-live,
  .dark .app-status-success {
    @apply text-positive-dark;
  }

  .app-status-warning {
    @apply text-warning-light;
  }

  .dark .app-status-warning {
    @apply text-warning-dark;
  }

  .app-status-error {
    @apply text-negative-light;
  }

  .dark .app-status-error {
    @apply text-negative-dark;
  }

  .app-input {
    @apply min-h-11 w-full rounded-control border border-border-light bg-surface-light px-3 py-2 text-text-light placeholder:text-muted-light focus:border-accent-light;
  }

  .dark .app-input {
    @apply border-border-dark bg-surface-dark text-text-dark placeholder:text-muted-dark focus:border-accent-dark;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }
}
```

Keep page-specific legacy component classes below this new layer until their pages migrate. Remove only conflicting definitions for `.card-base`, `.card-hover`, `.btn-primary`, `.btn-secondary`, `.btn-gradient`, `.section-container`, `.section-title`, `.nav-link-base`, `.site-banner`, `.input-base`, and `.textarea-base`.

- [ ] **Step 5: Build Tailwind and verify GREEN**

Run from the repository root:

```bash
npm run build:prod
```

Expected: exit 0 and regenerated `pickem/pickem_homepage/static/css/tailwind.css`.

Then run:

```bash
cd pickem
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.FrontendTokenContractTests -v 2
```

Expected: PASS.

- [ ] **Step 6: Commit the token foundation**

```bash
git add \
  tailwind.config.js \
  pickem/pickem_homepage/static/css/input.css \
  pickem/pickem_homepage/static/css/tailwind.css \
  pickem/pickem_homepage/test_homepage_redesign.py
git diff --cached --stat
git commit -m "feat: add broadcast blue design tokens"
```

## Task 3: Extract the Shared Application Shell

**Files:**
- Create: `pickem/pickem_homepage/templates/pickem/components/primary_nav.html`
- Create: `pickem/pickem_homepage/templates/pickem/components/mobile_nav.html`
- Create: `pickem/pickem_homepage/templates/pickem/components/site_banner.html`
- Create: `pickem/pickem_homepage/static/js/site-shell.js`
- Modify: `pickem/pickem_homepage/templates/pickem/base.html:20-605`
- Test: `pickem/pickem_homepage/test_homepage_redesign.py`

- [ ] **Step 1: Write failing shell rendering tests**

Append:

```python
class SharedShellRenderingTests(HomepageRedesignTestCase):
    def test_shell_uses_labeled_navigation_and_external_script(self):
        response = self.client.get("/")
        html = response.content.decode()

        self.assertContains(response, 'aria-label="Primary navigation"')
        self.assertContains(response, ">Home<")
        self.assertContains(response, ">Picks<")
        self.assertContains(response, ">Scores<")
        self.assertContains(response, ">Standings<")
        self.assertContains(response, 'js/site-shell.js')
        self.assertNotIn("function toggleDropdown", html)

    def test_shell_has_theme_toggle_with_pressed_state(self):
        response = self.client.get("/")

        self.assertContains(response, 'data-theme-toggle')
        self.assertContains(response, 'aria-pressed="false"')

    def test_authenticated_shell_does_not_render_fixed_bottom_bar(self):
        self.client.force_login(self.user)

        response = self.client.get("/")

        self.assertNotContains(response, 'class="fixed bottom-0')
```

- [ ] **Step 2: Run shell tests and verify RED**

```bash
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.SharedShellRenderingTests -v 2
```

Expected: FAIL because navigation is icon-only, scripts are inline, no theme-toggle contract exists, and the fixed bottom bar is present.

- [ ] **Step 3: Create the primary navigation include**

Create `templates/pickem/components/primary_nav.html`:

```django
{% load static socialaccount %}
<header class="sticky top-0 z-50">
  <div class="bg-nav-light text-white dark:bg-nav-dark">
    <div class="mx-auto flex h-7 max-w-7xl items-center gap-4 px-4 text-[0.6875rem] font-semibold uppercase tracking-wide text-white/60 sm:px-6">
      <span class="text-white">Family Pickem</span>
      <span>NFL</span>
      <span>Week {{ current_week|default:"--" }}</span>
    </div>
  </div>

  <nav
    class="border-b border-border-light bg-surface-light dark:border-border-dark dark:bg-surface-dark"
    aria-label="Primary navigation"
  >
    <div class="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
      <div class="flex items-center gap-5">
        <a href="/" class="flex items-center gap-2 font-bold" aria-label="Family Pickem home">
          <img src="{% static 'images/logo.png' %}" alt="" class="h-8 w-auto">
          <span class="hidden sm:inline">Family Pickem</span>
        </a>

        <div class="hidden items-stretch gap-1 md:flex">
          <a href="/" class="app-nav-link">Home</a>
          <a href="{% url 'game_picks' %}" class="app-nav-link">Picks</a>
          <a href="{% url 'scores' %}" class="app-nav-link">Scores</a>
          <a href="{% url 'standings' %}" class="app-nav-link">Standings</a>
          <a href="{% url 'rules' %}" class="app-nav-link">Rules</a>
          {% if user_is_commissioner %}
            <a href="{% url 'commissioners' %}" class="app-nav-link">Commissioner</a>
          {% endif %}
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          class="app-icon-button"
          data-theme-toggle
          aria-label="Toggle dark theme"
          aria-pressed="{% if user_theme_preference == 'dark' %}true{% else %}false{% endif %}"
        >
          <i class="fas fa-moon" aria-hidden="true"></i>
        </button>

        {% if user.is_authenticated %}
          <div class="relative" data-menu>
            <button
              type="button"
              class="app-account-button"
              data-menu-trigger
              aria-expanded="false"
              aria-controls="account-menu"
            >
              <span>{{ user.first_name|default:user.username }}</span>
              <i class="fas fa-chevron-down text-xs" aria-hidden="true"></i>
            </button>
            <div id="account-menu" class="app-menu hidden" data-menu-panel>
              <a href="{% url 'user_profile' user.id %}">My profile</a>
              <a href="{% url 'profile' %}">Settings</a>
              <a href="/logout">Sign out</a>
            </div>
          </div>
        {% else %}
          <a class="app-button-primary" href="{% provider_login_url 'google' %}">
            Sign in
          </a>
        {% endif %}

        <button
          type="button"
          class="app-icon-button md:hidden"
          data-mobile-menu-trigger
          aria-label="Open navigation"
          aria-expanded="false"
          aria-controls="mobile-navigation"
        >
          <i class="fas fa-bars" aria-hidden="true"></i>
        </button>
      </div>
    </div>
  </nav>
</header>
```

- [ ] **Step 4: Create the mobile navigation include**

Create `templates/pickem/components/mobile_nav.html`:

```django
<nav
  id="mobile-navigation"
  class="hidden border-b border-border-light bg-surface-light px-4 py-3 dark:border-border-dark dark:bg-surface-dark md:hidden"
  aria-label="Mobile navigation"
  data-mobile-menu
>
  <div class="grid gap-1">
    <a href="/" class="app-mobile-nav-link">Home</a>
    <a href="{% url 'game_picks' %}" class="app-mobile-nav-link">Picks</a>
    <a href="{% url 'scores' %}" class="app-mobile-nav-link">Scores</a>
    <a href="{% url 'standings' %}" class="app-mobile-nav-link">Standings</a>
    <a href="{% url 'rules' %}" class="app-mobile-nav-link">Rules</a>
    {% if user_is_commissioner %}
      <a href="{% url 'commissioners' %}" class="app-mobile-nav-link">Commissioner</a>
    {% endif %}
  </div>
</nav>
```

- [ ] **Step 5: Create the site banner include**

Create `templates/pickem/components/site_banner.html`:

```django
{% if active_banner %}
  <aside
    class="border-b border-border-light bg-surface-subtle-light dark:border-border-dark dark:bg-surface-subtle-dark"
    data-site-banner
    data-banner-key="banner-{{ active_banner.id }}"
    role="status"
  >
    <div class="mx-auto flex max-w-7xl items-start gap-3 px-4 py-3 sm:px-6">
      <div class="min-w-0 flex-1">
        <p class="text-sm font-semibold">{{ active_banner.title }}</p>
        {% if active_banner.description %}
          <p class="mt-0.5 text-sm text-muted-light dark:text-muted-dark">
            {{ active_banner.description }}
          </p>
        {% endif %}
      </div>
      {% if active_banner.show_close_button %}
        <button type="button" class="app-icon-button" data-banner-close aria-label="Dismiss announcement">
          <i class="fas fa-times" aria-hidden="true"></i>
        </button>
      {% endif %}
    </div>
  </aside>
{% elif banner_message %}
  <aside
    class="border-b border-border-light bg-surface-subtle-light dark:border-border-dark dark:bg-surface-subtle-dark"
    data-site-banner
    data-banner-key="site-banner"
    role="status"
  >
    <div class="mx-auto flex max-w-7xl items-start gap-3 px-4 py-3 sm:px-6">
      <div class="min-w-0 flex-1 text-sm">{{ banner_message|safe }}</div>
      {% if banner_dismissible %}
        <button type="button" class="app-icon-button" data-banner-close aria-label="Dismiss announcement">
          <i class="fas fa-times" aria-hidden="true"></i>
        </button>
      {% endif %}
    </div>
  </aside>
{% endif %}
```

- [ ] **Step 6: Add shell component classes**

Add inside `@layer components` in `input.css`:

```css
.app-nav-link {
  @apply flex h-14 items-center border-b-2 border-transparent px-2 text-sm font-semibold text-muted-light hover:text-text-light;
}

.dark .app-nav-link {
  @apply text-muted-dark hover:text-text-dark;
}

.app-nav-link[aria-current="page"] {
  @apply border-accent-light text-accent-light;
}

.dark .app-nav-link[aria-current="page"] {
  @apply border-accent-dark text-accent-dark;
}

.app-mobile-nav-link {
  @apply flex min-h-11 items-center rounded-control px-3 text-sm font-semibold hover:bg-surface-subtle-light;
}

.dark .app-mobile-nav-link {
  @apply hover:bg-surface-subtle-dark;
}

.app-icon-button {
  @apply inline-flex min-h-11 min-w-11 items-center justify-center rounded-control text-muted-light hover:bg-surface-subtle-light hover:text-text-light;
}

.dark .app-icon-button {
  @apply text-muted-dark hover:bg-surface-subtle-dark hover:text-text-dark;
}

.app-account-button {
  @apply hidden min-h-11 items-center gap-2 rounded-control px-3 text-sm font-semibold hover:bg-surface-subtle-light sm:inline-flex;
}

.dark .app-account-button {
  @apply hover:bg-surface-subtle-dark;
}

.app-menu {
  @apply absolute right-0 top-full mt-1 w-44 rounded-control border border-border-light bg-surface-light p-1 shadow-lg;
}

.dark .app-menu {
  @apply border-border-dark bg-surface-dark;
}

.app-menu a {
  @apply block rounded-control px-3 py-2 text-sm hover:bg-surface-subtle-light;
}

.dark .app-menu a {
  @apply hover:bg-surface-subtle-dark;
}
```

- [ ] **Step 7: Create the shell JavaScript**

Create `static/js/site-shell.js`:

```javascript
(() => {
  const root = document.documentElement;
  const themeToggle = document.querySelector('[data-theme-toggle]');
  const mobileTrigger = document.querySelector('[data-mobile-menu-trigger]');
  const mobileMenu = document.querySelector('[data-mobile-menu]');

  const setTheme = (theme, sync = true) => {
    const isDark = theme === 'dark';
    root.classList.toggle('dark', isDark);
    localStorage.setItem('theme', theme);

    if (themeToggle) {
      themeToggle.setAttribute('aria-pressed', String(isDark));
      themeToggle.setAttribute(
        'aria-label',
        isDark ? 'Switch to light theme' : 'Switch to dark theme'
      );
    }

    if (sync && document.body.dataset.authenticated === 'true') {
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
      if (csrfToken) {
        fetch('/toggle-theme/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ theme }),
        }).catch(() => {});
      }
    }
  };

  themeToggle?.addEventListener('click', () => {
    setTheme(root.classList.contains('dark') ? 'light' : 'dark');
  });

  mobileTrigger?.addEventListener('click', () => {
    const isOpen = mobileTrigger.getAttribute('aria-expanded') === 'true';
    mobileTrigger.setAttribute('aria-expanded', String(!isOpen));
    mobileMenu?.classList.toggle('hidden', isOpen);
  });

  document.querySelectorAll('[data-menu]').forEach((menu) => {
    const trigger = menu.querySelector('[data-menu-trigger]');
    const panel = menu.querySelector('[data-menu-panel]');
    trigger?.addEventListener('click', () => {
      const isOpen = trigger.getAttribute('aria-expanded') === 'true';
      trigger.setAttribute('aria-expanded', String(!isOpen));
      panel?.classList.toggle('hidden', isOpen);
    });
  });

  document.addEventListener('click', (event) => {
    document.querySelectorAll('[data-menu]').forEach((menu) => {
      if (!menu.contains(event.target)) {
        menu.querySelector('[data-menu-trigger]')?.setAttribute('aria-expanded', 'false');
        menu.querySelector('[data-menu-panel]')?.classList.add('hidden');
      }
    });
  });

  document.querySelectorAll('[data-site-banner]').forEach((banner) => {
    const key = `banner-dismissed-${banner.dataset.bannerKey}`;
    if (sessionStorage.getItem(key) === 'true') {
      banner.hidden = true;
    }
    banner.querySelector('[data-banner-close]')?.addEventListener('click', () => {
      sessionStorage.setItem(key, 'true');
      banner.hidden = true;
    });
  });

  window.FamilyPickemTheme = { setTheme };
})();
```

- [ ] **Step 8: Rebuild `base.html` around the includes**

Keep analytics, metadata, favicon, Font Awesome, Tailwind, `{% block title %}`, `{% block banner %}`, and `{% block content %}`.

Use this body structure:

```django
<body
  data-authenticated="{% if user.is_authenticated %}true{% else %}false{% endif %}"
>
  {% load socialaccount static %}
  {% include "pickem/components/primary_nav.html" %}
  {% include "pickem/components/mobile_nav.html" %}

  {% block banner %}
    {% include "pickem/components/site_banner.html" %}
  {% endblock %}

  <main class="min-h-[calc(100vh-5.25rem)]" id="main-content">
    {% block content %}{% endblock %}
  </main>

  <script src="{% static 'js/site-shell.js' %}" defer></script>
  {% block page_scripts %}{% endblock %}
</body>
```

Also:

- Change the Google Fonts request to Inter only, weights `400;500;600;700;800`.
- Add a skip link before the header:

```django
<a class="sr-only focus:not-sr-only" href="#main-content">Skip to content</a>
```

- Remove the fixed bottom status bar.
- Remove all inline dropdown, mobile menu, banner, and theme scripts.
- Add an early head script before styles to prevent theme flash:

```django
<script>
  (() => {
    const storedTheme = localStorage.getItem('theme');
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
    const serverTheme = '{{ user_theme_preference|default:"" }}';
    if ((serverTheme || storedTheme || systemTheme) === 'dark') {
      document.documentElement.classList.add('dark');
    }
  })();
</script>
```

- [ ] **Step 9: Build and verify GREEN**

```bash
npm run build:prod
cd pickem
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.SharedShellRenderingTests -v 2
```

Expected: Tailwind build exits 0 and all shell tests pass.

- [ ] **Step 10: Commit the shared shell**

```bash
git add \
  pickem/pickem_homepage/templates/pickem/base.html \
  pickem/pickem_homepage/templates/pickem/components/primary_nav.html \
  pickem/pickem_homepage/templates/pickem/components/mobile_nav.html \
  pickem/pickem_homepage/templates/pickem/components/site_banner.html \
  pickem/pickem_homepage/static/js/site-shell.js \
  pickem/pickem_homepage/static/css/input.css \
  pickem/pickem_homepage/static/css/tailwind.css \
  pickem/pickem_homepage/test_homepage_redesign.py
git diff --cached --stat
git commit -m "feat: rebuild shared application shell"
```

## Task 4: Build a Template-Ready Homepage Dashboard

**Files:**
- Create: `pickem/pickem_homepage/homepage_dashboard.py`
- Modify: `pickem/pickem_homepage/views.py:57-289`
- Test: `pickem/pickem_homepage/test_homepage_redesign.py`

- [ ] **Step 1: Write failing dashboard builder tests**

Append:

```python
from pickem_homepage.homepage_dashboard import build_homepage_dashboard


class HomepageDashboardBuilderTests(HomepageRedesignTestCase):
    def test_anonymous_dashboard_has_sign_in_action(self):
        dashboard = build_homepage_dashboard(
            user=None,
            total_games=1,
            user_picks_count=0,
            standings=[],
            games=[],
            activity=[],
        )

        self.assertEqual(dashboard["pick_status"]["state"], "anonymous")
        self.assertEqual(dashboard["pick_status"]["action_label"], "Sign in")

    def test_partial_pick_status_reports_remaining_games(self):
        dashboard = build_homepage_dashboard(
            user=self.user,
            total_games=4,
            user_picks_count=1,
            standings=[],
            games=[],
            activity=[],
        )

        self.assertEqual(dashboard["pick_status"]["state"], "partial")
        self.assertEqual(dashboard["pick_status"]["remaining"], 3)
        self.assertEqual(dashboard["pick_status"]["action_label"], "Continue picks")

    def test_complete_pick_status_offers_review(self):
        dashboard = build_homepage_dashboard(
            user=self.user,
            total_games=1,
            user_picks_count=1,
            standings=[],
            games=[],
            activity=[],
        )

        self.assertEqual(dashboard["pick_status"]["state"], "complete")
        self.assertEqual(dashboard["pick_status"]["action_label"], "Review picks")

    def test_current_user_summary_is_derived_from_standings(self):
        standings = [
            {"user_id": self.other_user.id, "name": "Mike", "total": 36, "week": 11},
            {"user_id": self.user.id, "name": "Jim", "total": 38, "week": 12},
        ]

        dashboard = build_homepage_dashboard(
            user=self.user,
            total_games=1,
            user_picks_count=0,
            standings=standings,
            games=[],
            activity=[],
        )

        self.assertEqual(dashboard["season_summary"]["rank"], 2)
        self.assertEqual(dashboard["season_summary"]["points"], 38)
        self.assertEqual(dashboard["season_summary"]["week_points"], 12)
```

- [ ] **Step 2: Run builder tests and verify RED**

```bash
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.HomepageDashboardBuilderTests -v 2
```

Expected: ERROR with `ModuleNotFoundError: pickem_homepage.homepage_dashboard`.

- [ ] **Step 3: Implement the pure dashboard builder**

Create `homepage_dashboard.py`:

```python
def _build_pick_status(user, total_games, user_picks_count):
    if user is None or not getattr(user, "is_authenticated", False):
        return {
            "state": "anonymous",
            "submitted": 0,
            "total": total_games,
            "remaining": total_games,
            "action_label": "Sign in",
            "action_url": "/accounts/google/login/",
        }

    remaining = max(total_games - user_picks_count, 0)
    if total_games > 0 and remaining == 0:
        state = "complete"
        action_label = "Review picks"
    elif user_picks_count > 0:
        state = "partial"
        action_label = "Continue picks"
    else:
        state = "pending"
        action_label = "Start picks"

    return {
        "state": state,
        "submitted": user_picks_count,
        "total": total_games,
        "remaining": remaining,
        "action_label": action_label,
        "action_url": "/picks/",
    }


def _build_season_summary(user, standings):
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    for rank, row in enumerate(standings, start=1):
        if row["user_id"] == user.id:
            return {
                "rank": rank,
                "points": row["total"],
                "week_points": row["week"],
            }
    return {"rank": None, "points": 0, "week_points": 0}


def build_homepage_dashboard(
    *,
    user,
    total_games,
    user_picks_count,
    standings,
    games,
    activity,
):
    return {
        "pick_status": _build_pick_status(
            user,
            total_games,
            user_picks_count,
        ),
        "season_summary": _build_season_summary(user, standings),
        "standings": standings,
        "games": games,
        "activity": activity,
    }
```

- [ ] **Step 4: Run builder tests and verify GREEN**

```bash
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.HomepageDashboardBuilderTests -v 2
```

Expected: PASS.

- [ ] **Step 5: Add failing index-context tests**

Append:

```python
class HomepageDashboardContextTests(HomepageRedesignTestCase):
    def test_index_exposes_template_ready_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get("/")

        dashboard = response.context["dashboard"]
        self.assertEqual(dashboard["pick_status"]["total"], 1)
        self.assertEqual(dashboard["season_summary"]["points"], 38)
        self.assertEqual(len(dashboard["standings"]), 2)
        self.assertEqual(dashboard["games"][0]["away_name"], "Buffalo Bills")
        self.assertEqual(dashboard["games"][0]["home_name"], "New York Jets")

    def test_index_preserves_week_points_inside_standings_rows(self):
        GamePicks.objects.create(
            id="jim-correct-pick",
            pick_game_id=self.game.id,
            slug=self.game.slug,
            uid=self.user.id,
            userID=str(self.user.id),
            userEmail=self.user.email,
            gameseason=2526,
            gameWeek="1",
            gameyear="2025",
            competition="nfl",
            pick="bills",
            pick_correct=True,
        )

        response = self.client.get("/")

        jim_row = next(
            row
            for row in response.context["dashboard"]["standings"]
            if row["user_id"] == self.user.id
        )
        self.assertEqual(jim_row["week"], 1)
```

- [ ] **Step 6: Run context tests and verify RED**

```bash
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.HomepageDashboardContextTests -v 2
```

Expected: FAIL with missing `dashboard` context.

- [ ] **Step 7: Adapt `index()` to build dashboard rows**

Import:

```python
from pickem_homepage.homepage_dashboard import build_homepage_dashboard
```

After the existing week-points query, construct the lookup:

```python
week_points_by_user = {
    row["uid"]: row["wins"]
    for row in week_points
}
```

Replace the duplicate rank-building loops with:

```python
standings_rows = []
for points in userSeasonPoints.objects.filter(
    gameseason=gameseason
).order_by("-total_points")[:10]:
    try:
        user_id = int(points.userID)
    except (TypeError, ValueError):
        continue

    player = User.objects.filter(id=user_id).only(
        "id",
        "username",
        "first_name",
    ).first()
    if player is None:
        continue

    standings_rows.append(
        {
            "user_id": user_id,
            "name": player.first_name or player.username,
            "week": week_points_by_user.get(user_id, 0),
            "total": points.total_points or 0,
        }
    )
```

Build compact game rows from current-week games:

```python
dashboard_games = []
for game in GamesAndScores.objects.filter(
    gameseason=gameseason,
    gameWeek=current_week,
    competition=current_competition,
).order_by("startTimestamp")[:6]:
    dashboard_games.append(
        {
            "id": game.id,
            "status_type": game.statusType,
            "status_title": game.statusTitle,
            "start": game.startTimestamp,
            "away_name": game.awayTeamName,
            "away_slug": game.awayTeamSlug,
            "away_score": game.awayTeamScore,
            "home_name": game.homeTeamName,
            "home_slug": game.homeTeamSlug,
            "home_score": game.homeTeamScore,
            "winner": game.gameWinner,
            "spread": game.spread,
        }
    )
```

Use recent message posts as activity:

```python
activity_rows = [
    {
        "text": post.title or post.content[:80],
        "created_at": post.created_at,
        "author": post.user.first_name or post.user.username,
    }
    for post in message_posts[:3]
]
```

Build and add the context:

```python
dashboard = build_homepage_dashboard(
    user=request.user if request.user.is_authenticated else None,
    total_games=current_games,
    user_picks_count=user_picks_count,
    standings=standings_rows,
    games=dashboard_games,
    activity=activity_rows,
)
```

Add `"dashboard": dashboard` to `context`.

Keep the existing message-board context and legacy context keys until the homepage template migration is complete. Do not remove the user's week-points keys in this task.

- [ ] **Step 8: Run context and characterization tests**

```bash
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.HomepageDashboardBuilderTests \
pickem_homepage.test_homepage_redesign.HomepageDashboardContextTests \
pickem_homepage.test_homepage_redesign.HomepageExistingBehaviorTests -v 2
```

Expected: PASS.

- [ ] **Step 9: Commit the dashboard view model**

```bash
git add \
  pickem/pickem_homepage/homepage_dashboard.py \
  pickem/pickem_homepage/views.py \
  pickem/pickem_homepage/test_homepage_redesign.py
git diff --cached --stat
git commit -m "feat: provide homepage dashboard view model"
```

## Task 5: Rebuild the Homepage from Small Components

**Files:**
- Create: `pickem/pickem_homepage/templates/pickem/components/module_header.html`
- Create: `pickem/pickem_homepage/templates/pickem/components/status_label.html`
- Create: `pickem/pickem_homepage/templates/pickem/components/home_pick_status.html`
- Create: `pickem/pickem_homepage/templates/pickem/components/home_game_row.html`
- Create: `pickem/pickem_homepage/templates/pickem/components/home_season_summary.html`
- Create: `pickem/pickem_homepage/templates/pickem/components/home_standings.html`
- Create: `pickem/pickem_homepage/templates/pickem/components/home_activity.html`
- Create: `pickem/pickem_homepage/templates/pickem/components/home_message_board.html`
- Create: `pickem/pickem_homepage/static/js/home-message-board.js`
- Modify: `pickem/pickem_homepage/templates/pickem/home.html`
- Modify: `pickem/pickem_homepage/static/css/input.css`
- Modify generated: `pickem/pickem_homepage/static/css/tailwind.css`
- Test: `pickem/pickem_homepage/test_homepage_redesign.py`

- [ ] **Step 1: Write failing homepage structure tests**

Append:

```python
class HomepageTemplateStructureTests(HomepageRedesignTestCase):
    def test_homepage_uses_approved_dashboard_hierarchy(self):
        response = self.client.get("/")

        self.assertContains(response, 'data-homepage-dashboard')
        self.assertContains(response, "Week 1")
        self.assertContains(response, "This week's games")
        self.assertContains(response, "League standings")
        self.assertContains(response, "League activity")

    def test_homepage_has_no_decorative_hero_contracts(self):
        response = self.client.get("/")
        html = response.content.decode()

        self.assertNotIn("bg-gradient-to-br", html)
        self.assertNotIn("-webkit-text-stroke", html)
        self.assertNotIn("shadow-glow", html)
        self.assertNotIn("backdrop-blur", html)
        self.assertNotIn("hover:scale", html)

    def test_anonymous_homepage_has_compact_sign_in_prompt(self):
        response = self.client.get("/")

        self.assertContains(response, "Sign in to make picks")
        self.assertContains(response, ">Sign in<")

    def test_authenticated_homepage_shows_pick_progress(self):
        self.client.force_login(self.user)

        response = self.client.get("/")

        self.assertContains(response, "0 of 1 complete")
        self.assertContains(response, ">Start picks<")

    def test_homepage_standings_use_table_semantics(self):
        response = self.client.get("/")

        self.assertContains(response, "<table", html=True)
        self.assertContains(response, 'scope="col"')
        self.assertContains(response, "Jim")
        self.assertContains(response, "38")

    def test_message_board_hooks_and_external_script_are_preserved(self):
        response = self.client.get("/")
        html = response.content.decode()

        self.assertContains(response, 'id="message-board-posts"')
        self.assertContains(response, 'js/home-message-board.js')
        self.assertIn("/message-board/create-post/", html)
        self.assertIn("/message-board/create-comment/", html)
        self.assertIn("/message-board/vote-post/", html)
        self.assertNotIn("// Message Board functionality", html)
```

- [ ] **Step 2: Run structure tests and verify RED**

```bash
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.HomepageTemplateStructureTests -v 2
```

Expected: FAIL because the old hero/card homepage is still rendered.

- [ ] **Step 3: Create generic module-header and status components**

Create `components/module_header.html`:

```django
<div class="app-module-header">
  <h2 class="app-module-title">{{ title }}</h2>
  {% if action_url and action_label %}
    <a class="app-link text-xs" href="{{ action_url }}">{{ action_label }}</a>
  {% endif %}
</div>
```

Create `components/status_label.html`:

```django
<span class="app-status app-status-{{ tone|default:'neutral' }}">
  {% if dot %}
    <span class="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true"></span>
  {% endif %}
  {{ label }}
</span>
```

- [ ] **Step 4: Create the pick-status component**

Create `components/home_pick_status.html`:

```django
<section class="app-module border-l-4 border-l-accent-light dark:border-l-accent-dark">
  <div class="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
    <div>
      <p class="text-xs font-semibold uppercase tracking-wide text-muted-light dark:text-muted-dark">
        Your picks
      </p>
      {% if dashboard.pick_status.state == "anonymous" %}
        <h2 class="mt-1 text-lg font-bold">Sign in to make picks</h2>
        <p class="mt-1 text-sm text-muted-light dark:text-muted-dark">
          Follow the week and join the family standings.
        </p>
      {% else %}
        <h2 class="mt-1 text-lg font-bold tabular-nums">
          {{ dashboard.pick_status.submitted }} of {{ dashboard.pick_status.total }} complete
        </h2>
        <p class="mt-1 text-sm text-muted-light dark:text-muted-dark">
          {% if dashboard.pick_status.state == "complete" %}
            All selections are saved.
          {% else %}
            {{ dashboard.pick_status.remaining }} selection{{ dashboard.pick_status.remaining|pluralize }} remaining.
          {% endif %}
        </p>
      {% endif %}
    </div>
    <a class="app-button-primary shrink-0" href="{{ dashboard.pick_status.action_url }}">
      {{ dashboard.pick_status.action_label }}
    </a>
  </div>
</section>
```

- [ ] **Step 5: Create the compact game-row component**

Create `components/home_game_row.html`:

```django
<article class="border-b border-border-light px-3 py-3 last:border-b-0 dark:border-border-dark">
  <div class="mb-2 flex items-center justify-between gap-3">
    {% if game.status_type == "inprogress" %}
      {% include "pickem/components/status_label.html" with label="Live" tone="live" dot=True only %}
    {% elif game.status_type == "finished" %}
      {% include "pickem/components/status_label.html" with label="Final" tone="success" only %}
    {% else %}
      {% include "pickem/components/status_label.html" with label=game.status_title tone="neutral" only %}
    {% endif %}
    <time class="text-xs text-muted-light dark:text-muted-dark" datetime="{{ game.start|date:'c' }}">
      {{ game.start|date:"D g:i A" }}
    </time>
  </div>

  <div class="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-sm tabular-nums">
    <span class="font-semibold">{{ game.away_name }}</span>
    <span class="font-bold">{{ game.away_score|default_if_none:"-" }}</span>
    <span class="font-semibold">{{ game.home_name }}</span>
    <span class="font-bold">{{ game.home_score|default_if_none:"-" }}</span>
  </div>

  {% if game.spread %}
    <p class="mt-2 text-xs text-muted-light dark:text-muted-dark">
      Spread: {{ game.spread }}
    </p>
  {% endif %}
</article>
```

- [ ] **Step 6: Create season summary, standings, and activity components**

Create `components/home_season_summary.html`:

```django
<section class="app-module">
  {% include "pickem/components/module_header.html" with title="Your season" only %}
  {% if dashboard.season_summary %}
    <dl class="grid grid-cols-3 divide-x divide-border-light dark:divide-border-dark">
      <div class="p-3">
        <dt class="text-xs uppercase tracking-wide text-muted-light dark:text-muted-dark">Rank</dt>
        <dd class="mt-1 text-xl font-bold tabular-nums">
          {% if dashboard.season_summary.rank %}{{ dashboard.season_summary.rank }}{% else %}-{% endif %}
        </dd>
      </div>
      <div class="p-3">
        <dt class="text-xs uppercase tracking-wide text-muted-light dark:text-muted-dark">Week</dt>
        <dd class="mt-1 text-xl font-bold tabular-nums">{{ dashboard.season_summary.week_points }}</dd>
      </div>
      <div class="p-3">
        <dt class="text-xs uppercase tracking-wide text-muted-light dark:text-muted-dark">Total</dt>
        <dd class="mt-1 text-xl font-bold tabular-nums">{{ dashboard.season_summary.points }}</dd>
      </div>
    </dl>
  {% else %}
    <p class="p-3 text-sm text-muted-light dark:text-muted-dark">Sign in to see your season.</p>
  {% endif %}
</section>
```

Create `components/home_standings.html`:

```django
<section class="app-module">
  {% include "pickem/components/module_header.html" with title="League standings" action_url="/standings/" action_label="Full table" only %}
  <div class="overflow-x-auto">
    <table class="w-full min-w-[28rem] text-left text-sm tabular-nums">
      <thead class="border-b border-border-light text-xs uppercase tracking-wide text-muted-light dark:border-border-dark dark:text-muted-dark">
        <tr>
          <th class="px-3 py-2" scope="col">Rank</th>
          <th class="px-3 py-2" scope="col">Player</th>
          <th class="px-3 py-2 text-right" scope="col">Week</th>
          <th class="px-3 py-2 text-right" scope="col">Total</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border-light dark:divide-border-dark">
        {% for row in dashboard.standings %}
          <tr>
            <td class="px-3 py-2 font-bold">{{ forloop.counter }}</td>
            <td class="px-3 py-2">
              <a class="font-semibold hover:text-accent-light dark:hover:text-accent-dark" href="{% url 'user_profile' row.user_id %}">
                {{ row.name }}
              </a>
            </td>
            <td class="px-3 py-2 text-right">{{ row.week }}</td>
            <td class="px-3 py-2 text-right font-bold">{{ row.total }}</td>
          </tr>
        {% empty %}
          <tr>
            <td class="px-3 py-5 text-center text-muted-light dark:text-muted-dark" colspan="4">
              Standings will appear after picks are scored.
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>
```

Create `components/home_activity.html`:

```django
<section class="app-module">
  {% include "pickem/components/module_header.html" with title="League activity" only %}
  <ol class="divide-y divide-border-light dark:divide-border-dark">
    {% for item in dashboard.activity %}
      <li class="px-3 py-3 text-sm">
        <p>{{ item.text }}</p>
        <p class="mt-1 text-xs text-muted-light dark:text-muted-dark">
          {{ item.author }} · {{ item.created_at|timesince }} ago
        </p>
      </li>
    {% empty %}
      <li class="px-3 py-4 text-sm text-muted-light dark:text-muted-dark">
        No recent league activity.
      </li>
    {% endfor %}
  </ol>
</section>
```

- [ ] **Step 7: Replace the homepage top-level template**

Before replacing `home.html`, mechanically extract the existing message board:

1. Move the complete DOM section beginning with `<!-- Message Board Section -->` at the current `home.html:511` through the closing element immediately before `<!-- Message Board JavaScript -->` into `components/home_message_board.html`.
2. Move the JavaScript inside the current message-board `<script>` block at `home.html:767-1263` into `static/js/home-message-board.js`, without its opening and closing `<script>` tags.
3. Preserve all endpoint strings, IDs, input names, CSRF handling, modal/disclosure hooks, and `data-*` attributes exactly during extraction.
4. Remove these decorative classes from the extracted HTML: gradients, glows, `hover:scale-*`, `rounded-2xl`, `rounded-3xl`, and forced uppercase usernames.
5. Give the extracted outer container `class="app-module"` and convert repeated post wrappers to `border-b border-border-light p-4 last:border-b-0 dark:border-border-dark`.

Then replace `home.html` with this structure:

```django
{% extends "pickem/base.html" %}
{% load static socialaccount pickem_homepage_extras %}

{% block title %}Week {{ current_week }} · Family Pickem{% endblock %}

{% block content %}
<div class="app-page" data-homepage-dashboard>
  <header class="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <p class="text-xs font-semibold uppercase tracking-wide text-muted-light dark:text-muted-dark">
        {% if current_competition == "nfl-preseason" %}Preseason{% else %}Regular season{% endif %}
      </p>
      <h1 class="mt-1 text-2xl font-extrabold tracking-tight sm:text-3xl">
        Week {{ current_week }}
      </h1>
    </div>
    <p class="text-sm text-muted-light dark:text-muted-dark">
      {{ current_games }} game{{ current_games|pluralize }} this week
    </p>
  </header>

  {% include "pickem/components/home_pick_status.html" %}

  <div class="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(18rem,0.75fr)]">
    <section class="app-module">
      {% include "pickem/components/module_header.html" with title="This week's games" action_url="/scores/" action_label="All scores" only %}
      <div>
        {% for game in dashboard.games %}
          {% include "pickem/components/home_game_row.html" with game=game only %}
        {% empty %}
          <p class="px-3 py-5 text-sm text-muted-light dark:text-muted-dark">
            No games are scheduled for this week yet.
          </p>
        {% endfor %}
      </div>
    </section>

    <div class="grid content-start gap-4">
      {% include "pickem/components/home_season_summary.html" %}
      {% include "pickem/components/home_activity.html" %}
    </div>
  </div>

  <div class="mt-4">
    {% include "pickem/components/home_standings.html" %}
  </div>

  <section class="mt-6" aria-labelledby="league-discussion-title">
    <div class="mb-3 flex items-center justify-between">
      <h2 id="league-discussion-title" class="text-lg font-bold">League discussion</h2>
    </div>
    {% include "pickem/components/home_message_board.html" %}
  </section>
</div>
{% endblock %}

{% block page_scripts %}
  <script src="{% static 'js/home-message-board.js' %}" defer></script>
{% endblock %}
```

Do not change message-board behavior in this slice.

- [ ] **Step 8: Build and run homepage tests**

```bash
npm run build:prod
cd pickem
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign -v 2
```

Expected: PASS.

- [ ] **Step 9: Run all homepage smoke and model tests**

```bash
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test pickem_homepage -v 2
```

Expected: PASS with zero failures.

- [ ] **Step 10: Commit the homepage reference implementation**

```bash
git add \
  pickem/pickem_homepage/templates/pickem/home.html \
  pickem/pickem_homepage/templates/pickem/components/module_header.html \
  pickem/pickem_homepage/templates/pickem/components/status_label.html \
  pickem/pickem_homepage/templates/pickem/components/home_pick_status.html \
  pickem/pickem_homepage/templates/pickem/components/home_game_row.html \
  pickem/pickem_homepage/templates/pickem/components/home_season_summary.html \
  pickem/pickem_homepage/templates/pickem/components/home_standings.html \
  pickem/pickem_homepage/templates/pickem/components/home_activity.html \
  pickem/pickem_homepage/templates/pickem/components/home_message_board.html \
  pickem/pickem_homepage/static/js/home-message-board.js \
  pickem/pickem_homepage/static/css/input.css \
  pickem/pickem_homepage/static/css/tailwind.css \
  pickem/pickem_homepage/test_homepage_redesign.py
git diff --cached --stat
git commit -m "feat: rebuild homepage as weekly dashboard"
```

## Task 6: Browser Validation, Accessibility Pass, and Final Verification

**Files:**
- Modify when a failing test or browser check identifies a defect: `pickem/pickem_homepage/templates/pickem/home.html`
- Modify when a failing test or browser check identifies a defect: `pickem/pickem_homepage/templates/pickem/components/*.html`
- Modify when a failing test or browser check identifies a defect: `pickem/pickem_homepage/static/css/input.css`
- Modify when a failing test or browser check identifies a defect: `pickem/pickem_homepage/static/js/site-shell.js`
- Modify when a failing test or browser check identifies a defect: `pickem/pickem_homepage/static/js/home-message-board.js`
- Modify generated after CSS changes: `static/css/tailwind.css`
- Test: `pickem/pickem_homepage/test_homepage_redesign.py`

- [ ] **Step 1: Add a static regression test against banned homepage treatments**

Append:

```python
class HomepageVisualRegressionContractTests(TestCase):
    def test_homepage_source_excludes_banned_decorative_treatments(self):
        project_root = Path(settings.BASE_DIR)
        sources = [
            project_root / "pickem_homepage/templates/pickem/home.html",
            project_root / "pickem_homepage/templates/pickem/components/home_pick_status.html",
            project_root / "pickem_homepage/templates/pickem/components/home_game_row.html",
            project_root / "pickem_homepage/templates/pickem/components/home_standings.html",
        ]
        combined = "\n".join(path.read_text() for path in sources)

        banned = [
            "bg-gradient",
            "backdrop-blur",
            "shadow-glow",
            "hover:scale",
            "-webkit-text-stroke",
            "rounded-2xl",
            "rounded-3xl",
        ]
        for treatment in banned:
            with self.subTest(treatment=treatment):
                self.assertNotIn(treatment, combined)
```

- [ ] **Step 2: Run the visual contract test**

```bash
DJANGO_SETTINGS_MODULE=pickem.test_settings \
python manage.py test \
pickem_homepage.test_homepage_redesign.HomepageVisualRegressionContractTests -v 2
```

Expected: PASS. If it fails, remove the banned treatment rather than weakening the test.

- [ ] **Step 3: Ensure the local containers use current source**

The current Docker image copies source at build time. Rebuild and restart the isolated review containers:

```bash
docker rm -f family-pickem-review-web family-pickem-review-db
docker compose run -d --name family-pickem-review-db --use-aliases postgresql
docker compose run -d --name family-pickem-review-web --use-aliases --no-deps -p 8000:8000 django
```

Expected: both containers start and `curl -I http://localhost:8000/` returns `HTTP/1.1 200 OK`.

- [ ] **Step 4: Validate the anonymous homepage in the in-app browser**

Open `http://localhost:8000/` and verify at desktop width:

- Utility bar, labeled primary navigation, and mobile trigger contracts exist.
- The week heading is the largest homepage text.
- The sign-in prompt is compact and immediately below the week heading.
- Games occupy the main column.
- Season summary and activity occupy the side column.
- Standings use a real table.
- No fixed bottom bar covers content.
- No gradients, glows, glass effects, outlined text, or hover scaling remain.
- Browser console has no new JavaScript errors.

- [ ] **Step 5: Validate both themes**

Use the theme toggle and verify:

- `aria-pressed` changes with theme state.
- `html.dark` is added and removed.
- Reload preserves the selected theme for anonymous users.
- Canvas, surfaces, borders, text, accent, and semantic statuses remain legible.
- Focus rings are visible in both themes.

- [ ] **Step 6: Validate mobile reflow**

At approximately `390x844`:

- No page-level horizontal scrolling occurs.
- Pick status, games, season summary, standings, and activity appear in the approved order.
- The mobile navigation opens, closes, and reports `aria-expanded`.
- Interactive controls have practical touch target size.
- The standings table either fits its scroll container or adapts without expanding the page.

- [ ] **Step 7: Validate authenticated states**

Create or use a local test user. Verify:

- Pending state says `0 of N complete` and `Start picks`.
- Partial state says `X of N complete`, reports remaining picks, and says `Continue picks`.
- Complete state says all selections are saved and says `Review picks`.
- Personal rank/week/total summary matches the standings row.
- Account menu opens and closes correctly.
- Existing message-board create/comment/vote behavior still works.

- [ ] **Step 8: Fix findings with test-first loops**

For each behavior defect:

1. Add a focused failing Django test or reproducible browser assertion.
2. Run it and confirm the expected failure.
3. Make the smallest implementation change.
4. Re-run the focused test.
5. Re-run `pickem_homepage.test_homepage_redesign`.

For purely visual spacing or color adjustments, update the relevant semantic token or component class, rebuild Tailwind, and re-check both themes and widths.

- [ ] **Step 9: Run the complete verification suite**

From the repository root:

```bash
npm run build:prod
cd pickem
DJANGO_SETTINGS_MODULE=pickem.test_settings python manage.py check
DJANGO_SETTINGS_MODULE=pickem.test_settings python manage.py test -v 2
```

Expected:

- Tailwind build exits 0.
- Django system check reports no issues.
- Full test suite reports zero failures and zero errors.

Then:

```bash
cd ..
git diff --check
git status --short
```

Expected:

- `git diff --check` exits 0.
- Only intended frontend files plus the user's unrelated `pickem/pickem_api/cron_update_records.py` change remain.

- [ ] **Step 10: Commit final homepage polish**

Stage only files changed by browser findings:

```bash
git add \
  pickem/pickem_homepage/templates/pickem \
  pickem/pickem_homepage/static/css/input.css \
  pickem/pickem_homepage/static/css/tailwind.css \
  pickem/pickem_homepage/static/js/site-shell.js \
  pickem/pickem_homepage/test_homepage_redesign.py
git diff --cached --stat
git commit -m "fix: polish homepage responsive states"
```

If browser validation required no changes, skip this commit.

## Completion Criteria

- Broadcast Blue semantic tokens are built and used by the shell and homepage.
- Light and dark themes share the same hierarchy and component structure.
- Navigation is labeled, keyboard operable, and responsive.
- Inline shell scripts and the fixed bottom status bar are removed.
- Homepage order matches the approved mockup on desktop and mobile.
- Existing week-points and message-board behavior are preserved.
- Homepage source contains none of the banned decorative treatments.
- Tailwind build, Django check, and full Django test suite pass.
- Browser validation covers anonymous/authenticated, light/dark, and desktop/mobile states.

## Follow-Up Plans

After this plan is merged or approved in-browser, write separate implementation plans in this order:

1. `frontend-picks-scores.md`
2. `frontend-standings-profiles.md`
3. `frontend-rules-settings-commissioner-cleanup.md`

Each follow-up plan reuses the semantic tokens, shell, modules, status labels, table patterns, JavaScript conventions, and browser-validation matrix established here.
