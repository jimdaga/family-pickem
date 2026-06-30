# Codebase Structure

**Analysis Date:** 2026-06-28

## Directory Layout

```text
family-pickem/
├── .github/workflows/          # Release, test, Docker, Helm, and ArgoCD automation
├── .planning/codebase/         # Generated codebase maps for GSD workflows
├── charts/family-pickem/       # Helm chart for the Django app and CronJob
├── cmd/                        # Go command source for auxiliary tooling
├── docker/app/                 # Django application container image and entrypoint
├── docs/superpowers/           # Planning/spec artifacts for prior workflow phases
├── hack/                       # CSV seed data and shell scripts for teams/weeks
├── infra/                      # ArgoCD, External Secrets, ingress, MetalLB, backup manifests
├── pickem/                     # Django project root
│   ├── manage.py               # Django CLI entry point
│   ├── requirements.txt        # Python dependencies
│   ├── pickem/                 # Django project package and shared config/utilities
│   ├── pickem_api/             # League data models, API endpoints, serializers, cron scripts
│   └── pickem_homepage/        # Browser views, templates, forms, community models, UI assets
├── tools/                      # Tailwind/CSS migration helper scripts
├── package.json                # Tailwind build commands and frontend dev dependencies
├── package-lock.json           # npm lockfile
└── tailwind.config.js          # Tailwind content paths and design tokens
```

## Directory Purposes

**Project Root:**
- Purpose: Repository-level documentation, package metadata, frontend build config, deployment directories.
- Contains: `AGENTS.md`, `CLAUDE.md`, `README.md`, `STYLE_GUIDE.md`, `package.json`, `tailwind.config.js`.
- Key files: `package.json`, `tailwind.config.js`, `pickem/requirements.txt`.

**`pickem/`:**
- Purpose: Django application root.
- Contains: `manage.py`, project package, apps, requirements, Elastic Beanstalk config.
- Key files: `pickem/manage.py`, `pickem/requirements.txt`, `pickem/.ebextensions/`, `pickem/.elasticbeanstalk/config.yml`.

**`pickem/pickem/`:**
- Purpose: Django project package.
- Contains: Settings, URL router, WSGI/ASGI entry points, shared utilities, global template context processors, collected/static legacy assets.
- Key files: `pickem/pickem/settings.py`, `pickem/pickem/urls.py`, `pickem/pickem/utils.py`, `pickem/pickem/context_processors.py`, `pickem/pickem/wsgi.py`, `pickem/pickem/asgi.py`, `pickem/pickem/test_settings.py`.

**`pickem/pickem_api/`:**
- Purpose: League domain backend.
- Contains: ORM models, DRF serializers, function-based API views, API URLs, custom DRF permission, admin classes, migrations, tests, cron update scripts.
- Key files: `pickem/pickem_api/models.py`, `pickem/pickem_api/views.py`, `pickem/pickem_api/serializers.py`, `pickem/pickem_api/urls.py`, `pickem/pickem_api/permissions.py`, `pickem/pickem_api/admin.py`, `pickem/pickem_api/tests.py`.

**`pickem/pickem_api/migrations/`:**
- Purpose: Schema history for league domain models.
- Contains: 72+ migration files for games, teams, picks, points, stats, current season, user profiles.
- Key files: `pickem/pickem_api/migrations/0062_add_userprofile_model.py`, `pickem/pickem_api/migrations/0066_add_betting_weather_venue_fields.py`, `pickem/pickem_api/migrations/0071_userseasonpoints_current_rank.py`.

**`pickem/pickem_api/templates/api/`:**
- Purpose: API-specific template artifacts.
- Contains: `games.html`.
- Key files: `pickem/pickem_api/templates/api/games.html`.

**`pickem/pickem_api/static/`:**
- Purpose: API app static files.
- Contains: App-specific CSS.
- Key files: `pickem/pickem_api/static/css/site.css`.

**`pickem/pickem_homepage/`:**
- Purpose: User-facing Django app.
- Contains: Page/AJAX views, page URLs, forms, community/banner models, admin classes, migrations, tests, management commands, templates, static assets, template tags.
- Key files: `pickem/pickem_homepage/views.py`, `pickem/pickem_homepage/urls.py`, `pickem/pickem_homepage/forms.py`, `pickem/pickem_homepage/models.py`, `pickem/pickem_homepage/tests.py`.

**`pickem/pickem_homepage/templates/pickem/`:**
- Purpose: Django templates for browser pages.
- Contains: Base layout and pages for home, scores, standings, picks, profile, rules, commissioners, public/private user profiles.
- Key files: `pickem/pickem_homepage/templates/pickem/base.html`, `pickem/pickem_homepage/templates/pickem/home.html`, `pickem/pickem_homepage/templates/pickem/picks.html`, `pickem/pickem_homepage/templates/pickem/scores.html`, `pickem/pickem_homepage/templates/pickem/commissioners.html`.

**`pickem/pickem_homepage/static/`:**
- Purpose: App-owned frontend assets.
- Contains: Tailwind source/output CSS, legacy CSS/JS, team SVGs, icons, PNGs.
- Key files: `pickem/pickem_homepage/static/css/input.css`, `pickem/pickem_homepage/static/css/tailwind.css`, `pickem/pickem_homepage/static/css/style.css`, `pickem/pickem_homepage/static/css/dark-mode.js`, `pickem/pickem_homepage/static/images/logo.png`.

**`pickem/pickem_homepage/templatetags/`:**
- Purpose: Template filters and tags for presentation lookups.
- Contains: `pickem_homepage_extras.py`.
- Key files: `pickem/pickem_homepage/templatetags/pickem_homepage_extras.py`.

**`pickem/pickem_homepage/management/commands/`:**
- Purpose: Custom Django management commands.
- Contains: Superuser and site banner commands.
- Key files: `pickem/pickem_homepage/management/commands/createsu.py`, `pickem/pickem_homepage/management/commands/manage_banners.py`.

**`charts/family-pickem/`:**
- Purpose: Helm packaging for Kubernetes deployment.
- Contains: Chart metadata, values, deployment, service, ingress, HPA, secret, external secret, backup, and cron templates.
- Key files: `charts/family-pickem/Chart.yaml`, `charts/family-pickem/values.yaml`, `charts/family-pickem/templates/deployment.yaml`, `charts/family-pickem/templates/cronjob.yaml`, `charts/family-pickem/templates/service.yaml`, `charts/family-pickem/templates/ingress.yaml`.

**`infra/`:**
- Purpose: Cluster and GitOps configuration outside the app chart.
- Contains: ArgoCD apps, External Secrets, ingress-nginx values, MetalLB config, backup CronJob, environment-specific values.
- Key files: `infra/argocd/applications/pickem-dev.yaml`, `infra/argocd/applications/pickem-prd.yaml`, `infra/external-secrets/cluster-secret-store.yaml`, `infra/backup/backup-cronjob.yaml`, `infra/app/values-dev.yaml`, `infra/app/values-prd.yaml`.

**`docker/app/`:**
- Purpose: Container build and runtime startup for Django.
- Contains: Dockerfile and entrypoint script.
- Key files: `docker/app/Dockerfile`, `docker/app/docker-entrypoint.sh`.

**`tools/`:**
- Purpose: CSS/Tailwind migration analysis and conversion helpers.
- Contains: Python scripts for class scanning, legacy CSS extraction, and CSS-to-Tailwind mapping.
- Key files: `tools/css_class_scanner.py`, `tools/css_to_tailwind_mapper.py`, `tools/extract_legacy_css.py`.

**`hack/`:**
- Purpose: Manual seed/import helper data.
- Contains: Team CSV, week CSVs by season, shell scripts.
- Key files: `hack/teams.csv`, `hack/weeks-2324.csv`, `hack/weeks-2425.csv`, `hack/weeks-2526.csv`, `hack/add_teams.sh`, `hack/add_weeks.sh`.

## Key File Locations

**Entry Points:**
- `pickem/manage.py`: Django management entry point.
- `pickem/pickem/wsgi.py`: WSGI application entry point.
- `pickem/pickem/asgi.py`: ASGI application entry point.
- `pickem/pickem/urls.py`: Root URL dispatcher.
- `pickem/pickem_homepage/urls.py`: Browser page and AJAX routes.
- `pickem/pickem_api/urls.py`: REST API routes.
- `docker/app/docker-entrypoint.sh`: Container startup script.
- `charts/family-pickem/templates/cronjob.yaml`: Kubernetes scheduled-job entry point.

**Configuration:**
- `pickem/pickem/settings.py`: Main Django settings.
- `pickem/pickem/test_settings.py`: Test settings overlay.
- `pickem/requirements.txt`: Python dependencies.
- `package.json`: Tailwind build commands.
- `tailwind.config.js`: Tailwind content paths, colors, fonts, shadows, radii.
- `docker/app/Dockerfile`: Container image definition.
- `charts/family-pickem/values.yaml`: Helm default values.
- `infra/app/values-dev.yaml`: Development environment values.
- `infra/app/values-prd.yaml`: Production environment values.

**Core Logic:**
- `pickem/pickem_api/models.py`: League, pick, team, season, stats, and profile models.
- `pickem/pickem_homepage/models.py`: Banner and message-board models.
- `pickem/pickem_homepage/views.py`: Page rendering, profile logic, picks, message board, commissioner actions.
- `pickem/pickem_api/views.py`: API endpoint logic for games, weeks, picks, teams, points, current season.
- `pickem/pickem_homepage/forms.py`: Forms for picks, posts, comments, week winners, banners.
- `pickem/pickem_api/serializers.py`: DRF serializers for API payloads.
- `pickem/pickem/utils.py`: Season and pick-lock helpers.
- `pickem/pickem/context_processors.py`: Theme/banner/footer global context.

**Templates and Frontend:**
- `pickem/pickem_homepage/templates/pickem/base.html`: Shared layout, nav, auth links, static includes, banner block.
- `pickem/pickem_homepage/templates/pickem/home.html`: Homepage.
- `pickem/pickem_homepage/templates/pickem/picks.html`: Pick submission UI.
- `pickem/pickem_homepage/templates/pickem/scores.html`: Scores and weekly standings UI.
- `pickem/pickem_homepage/templates/pickem/standings.html`: Season leaderboard UI.
- `pickem/pickem_homepage/templates/pickem/profile.html`: User settings UI.
- `pickem/pickem_homepage/templates/pickem/user_profile.html`: Public profile UI.
- `pickem/pickem_homepage/templates/pickem/commissioners.html`: Commissioner dashboard.
- `pickem/pickem_homepage/static/css/input.css`: Tailwind source CSS.
- `pickem/pickem_homepage/static/css/tailwind.css`: Tailwind build output.

**Scheduled Jobs:**
- `pickem/pickem_api/cron_update_games_v2.py`: ESPN scoreboard ingestion and game updates.
- `pickem/pickem_api/cron_update_picks.py`: Correct-pick scoring for finished games.
- `pickem/pickem_api/cron_update_standings.py`: Weekly and total point updates.
- `pickem/pickem_api/cron_update_records.py`: ESPN team record updates.
- `pickem/pickem_api/cron_add_standings.py`: User season standing initialization.
- `pickem/pickem_api/cron_update_rankings.py`: Ranking updates.

**Testing:**
- `pickem/pickem_api/tests.py`: API app model/serializer tests.
- `pickem/pickem_homepage/tests.py`: View smoke tests, commissioner checks, season utility, banners, message board, management command tests.
- `pickem/pickem/test_settings.py`: Settings used by CI test command.
- `.github/workflows/publish-artifacts.yaml`: Runs `cd pickem && python manage.py test --settings=pickem.test_settings --verbosity=2`.

**Admin:**
- `pickem/pickem_api/admin.py`: Admin registration for league data, stats, current season, user profile.
- `pickem/pickem_homepage/admin.py`: Admin registration for site banners, posts, comments, votes.

**Deployment:**
- `charts/family-pickem/templates/deployment.yaml`: Django Deployment.
- `charts/family-pickem/templates/service.yaml`: Kubernetes Service.
- `charts/family-pickem/templates/ingress.yaml`: Kubernetes Ingress.
- `charts/family-pickem/templates/cronjob.yaml`: Update-data CronJob.
- `charts/family-pickem/templates/backup-cronjob.yaml`: Backup CronJob.
- `.github/workflows/publish-artifacts.yaml`: Release publishing workflow.
- `.github/workflows/publish-artifacts-latest.yaml`: Latest artifact workflow.

## Naming Conventions

**Files:**
- Django app modules use standard names: `models.py`, `views.py`, `urls.py`, `forms.py`, `admin.py`, `apps.py`, `tests.py`.
- Cron scripts use `cron_<verb>_<domain>.py`: `pickem/pickem_api/cron_update_games_v2.py`, `pickem/pickem_api/cron_update_standings.py`.
- Templates use page names under `templates/pickem/`: `home.html`, `scores.html`, `standings.html`, `picks.html`.
- Static CSS uses role names: `input.css` for Tailwind input and `tailwind.css` for generated output.
- Helm templates use Kubernetes resource names: `deployment.yaml`, `service.yaml`, `cronjob.yaml`, `ingress.yaml`.

**Directories:**
- Django app directories live under `pickem/` and use Python package names: `pickem_api`, `pickem_homepage`, `pickem`.
- Templates are namespaced by app/domain at `pickem/pickem_homepage/templates/pickem/`.
- Template tags live in `templatetags/` under the app that owns the templates.
- Management commands live in `management/commands/` under the app that owns the command.
- Kubernetes chart templates live in `charts/family-pickem/templates/`.

## Where to Add New Code

**New Browser Page:**
- Primary code: `pickem/pickem_homepage/views.py`
- Route: `pickem/pickem_homepage/urls.py`
- Template: `pickem/pickem_homepage/templates/pickem/<page>.html`
- Tests: `pickem/pickem_homepage/tests.py`

**New AJAX Endpoint for Existing Pages:**
- Primary code: `pickem/pickem_homepage/views.py`
- Route: `pickem/pickem_homepage/urls.py`
- Use JSON response patterns from `check_username`, `toggle_theme`, `create_comment`, or commissioner endpoints in `pickem/pickem_homepage/views.py`.
- Tests: `pickem/pickem_homepage/tests.py`

**New API Endpoint:**
- Primary code: `pickem/pickem_api/views.py`
- Route: `pickem/pickem_api/urls.py`
- Serializer: `pickem/pickem_api/serializers.py`
- Permission: `pickem/pickem_api/permissions.py` when default DRF permissions are not enough.
- Tests: `pickem/pickem_api/tests.py`

**New League Data Model:**
- Implementation: `pickem/pickem_api/models.py`
- Admin: `pickem/pickem_api/admin.py`
- Serializer: `pickem/pickem_api/serializers.py` if exposed through `/api/`.
- Migration: generated under `pickem/pickem_api/migrations/`.
- Tests: `pickem/pickem_api/tests.py`.

**New Community or Site UI Model:**
- Implementation: `pickem/pickem_homepage/models.py`
- Admin: `pickem/pickem_homepage/admin.py`
- Form: `pickem/pickem_homepage/forms.py`
- Migration: generated under `pickem/pickem_homepage/migrations/`.
- Tests: `pickem/pickem_homepage/tests.py`.

**New Form:**
- Implementation: `pickem/pickem_homepage/forms.py`
- Usage: `pickem/pickem_homepage/views.py`
- Template markup: `pickem/pickem_homepage/templates/pickem/<page>.html`.

**New Template Helper:**
- Shared filters/tags: `pickem/pickem_homepage/templatetags/pickem_homepage_extras.py`
- Use for repeated presentation lookups; keep expensive multi-row calculations in views when possible.

**New Shared Backend Utility:**
- Shared app utility: `pickem/pickem/utils.py`
- Use for cross-view rules such as season resolution and pick-lock logic.
- Do not put page rendering or API serialization code in `pickem/pickem/utils.py`.

**New Global Template Context:**
- Implementation: `pickem/pickem/context_processors.py`
- Registration: `TEMPLATES[0]['OPTIONS']['context_processors']` in `pickem/pickem/settings.py`.
- Use only for values needed across most templates.

**New Scheduled Job:**
- Script: `pickem/pickem_api/cron_<action>.py`
- Deployment command: `charts/family-pickem/values.yaml` and `charts/family-pickem/templates/cronjob.yaml` if it joins the main update job.
- API access: Use existing `/api/` endpoints or add endpoints in `pickem/pickem_api/views.py`.

**New Tailwind Styling:**
- Tokens/utilities: `pickem/pickem_homepage/static/css/input.css`
- Build output: `pickem/pickem_homepage/static/css/tailwind.css`
- Template classes: `pickem/pickem_homepage/templates/pickem/*.html`
- Build command: `npm run build:prod` from `package.json`.

**New Static Image Asset:**
- Primary location: `pickem/pickem_homepage/static/images/`
- Reference in templates with `{% static 'images/<file>' %}`.

**New Deployment Manifest:**
- App chart resource: `charts/family-pickem/templates/`
- Default values: `charts/family-pickem/values.yaml`
- Environment overrides: `infra/app/values-dev.yaml`, `infra/app/values-prd.yaml`
- ArgoCD app wiring: `infra/argocd/applications/`.

## Special Directories

**`.planning/codebase/`:**
- Purpose: Generated architecture, stack, testing, convention, integration, and concern maps for GSD commands.
- Generated: Yes
- Committed: Yes

**`pickem/pickem_api/migrations/`:**
- Purpose: Django migrations for API/domain models.
- Generated: Yes
- Committed: Yes

**`pickem/pickem_homepage/migrations/`:**
- Purpose: Django migrations for homepage/community models.
- Generated: Yes
- Committed: Yes

**`pickem/pickem_homepage/static/css/tailwind.css`:**
- Purpose: Built Tailwind CSS consumed by templates.
- Generated: Yes
- Committed: Yes

**`pickem/pickem/static/admin/` and `pickem/pickem/static/rest_framework/`:**
- Purpose: Collected/static vendor assets for Django admin and DRF browsable API.
- Generated: Yes
- Committed: Yes

**`node_modules/`:**
- Purpose: Installed npm dependencies for Tailwind tooling.
- Generated: Yes
- Committed: No

**`venv/`:**
- Purpose: Local Python virtual environment.
- Generated: Yes
- Committed: No

**`docs/superpowers/`:**
- Purpose: Workflow-generated specs and plans.
- Generated: Yes
- Committed: Yes

**`hack/`:**
- Purpose: Manual seed scripts and CSV source data for teams/weeks.
- Generated: No
- Committed: Yes

**`infra/argocd/`:**
- Purpose: ArgoCD and application manifests.
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-06-28*
