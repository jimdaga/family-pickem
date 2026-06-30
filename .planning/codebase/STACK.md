# Technology Stack

**Analysis Date:** 2026-06-28

## Languages

**Primary:**
- Python 3.10 - Django application, REST API, cron data-sync scripts, and container runtime in `docker/app/Dockerfile`, `pickem/manage.py`, `pickem/pickem/`, `pickem/pickem_api/`, and `pickem/pickem_homepage/`.
- HTML/CSS/JavaScript - Django templates and frontend behavior in `pickem/pickem_homepage/templates/pickem/`, `pickem/pickem_homepage/static/css/input.css`, and `pickem/pickem_homepage/static/js/`.

**Secondary:**
- Shell - Container startup and cron orchestration in `docker/app/docker-entrypoint.sh` and `pickem/pickem_api/cron.sh`.
- YAML - Docker Compose, Helm, Kubernetes, and GitHub Actions configuration in `docker-compose.yml`, `charts/family-pickem/`, and `.github/workflows/`.

## Runtime

**Environment:**
- Python 3.10 - Docker image base is `python:3.10` in `docker/app/Dockerfile`; GitHub Actions test setup uses `python-version: '3.10'` in `.github/workflows/publish-artifacts.yaml`.
- Django development server - `docker/app/docker-entrypoint.sh` runs `python manage.py runserver 0.0.0.0:8000`; local development uses `python manage.py runserver` from `pickem/`.
- Node.js - Used for Tailwind CSS build tooling through `npx tailwindcss`; no pinned Node version file is detected.

**Package Manager:**
- pip - Python dependencies are pinned in `pickem/requirements.txt`.
- npm - Frontend build dependencies are in `package.json`.
- Lockfile: `package-lock.json` present for npm; no Python lockfile detected.

## Frameworks

**Core:**
- Django 4.0.2 - Main web framework configured in `pickem/pickem/settings.py`, routed through `pickem/pickem/urls.py`, and split across `pickem/pickem_api/` and `pickem/pickem_homepage/`.
- Django REST Framework 3.13.1 - Internal JSON API configured in `pickem/pickem/settings.py`, routed in `pickem/pickem_api/urls.py`, and implemented in `pickem/pickem_api/views.py`.
- django-allauth 0.51.0 - Google OAuth login configured in `pickem/pickem/settings.py` and used by templates such as `pickem/pickem_homepage/templates/pickem/base.html`.
- Tailwind CSS 3.4.18 - Utility CSS build pipeline configured in `tailwind.config.js` and `package.json`.
- Bootstrap 5 - Template-era frontend framework via `django-bootstrap-v5==1.0.11` in `pickem/requirements.txt` and CDN includes in `pickem/pickem_homepage/templates/pickem/base.html`; this coexists with Tailwind during migration.

**Testing:**
- Django test runner - Tests run with `cd pickem && python manage.py test`; CI uses `python manage.py test --settings=pickem.test_settings --verbosity=2` in `.github/workflows/publish-artifacts.yaml`.
- Django test settings - Isolated test configuration in `pickem/pickem/test_settings.py` uses SQLite, local static storage, and a stable test-only secret key.

**Build/Dev:**
- Tailwind CLI - `npm run build:css` watches CSS and `npm run build:prod` minifies output to `pickem/pickem_homepage/static/css/tailwind.css`.
- PostCSS 8.5.6 and Autoprefixer 10.4.22 - Build-time CSS tooling declared in `package.json`.
- Docker Compose 3.8 - Local multi-container runtime in `docker-compose.yml`.
- Helm v2 chart API - Kubernetes deployment package in `charts/family-pickem/Chart.yaml`.
- GitHub Actions - Release testing, Docker publishing, Helm publishing, and ArgoCD target updates in `.github/workflows/publish-artifacts.yaml` and `.github/workflows/publish-artifacts-latest.yaml`.

## Key Dependencies

**Critical:**
- `Django==4.0.2` - Owns request routing, ORM models, templates, middleware, sessions, and admin in `pickem/pickem/settings.py`.
- `djangorestframework==3.13.1` - Powers `/api/` endpoints in `pickem/pickem_api/views.py` and serializers in `pickem/pickem_api/serializers.py`.
- `psycopg2-binary==2.9.3` - PostgreSQL driver used by `DATABASES` in `pickem/pickem/settings.py`.
- `django-allauth==0.51.0` - Social authentication backend and Google provider in `pickem/pickem/settings.py`.
- `requests==2.28.1` - HTTP client for ESPN data sync, internal API updates, and EC2 metadata lookup in `pickem/pickem_api/cron_update_games_v2.py`, `pickem/pickem_api/cron_update_records.py`, and `pickem/pickem/settings.py`.
- `espn-api==0.45.1` - ESPN fantasy/NFL package imported in `pickem/pickem_api/cron_update_games_v2.py`.

**Infrastructure:**
- `boto3==1.24.65`, `botocore==1.27.65`, `django-storages==1.13.1` - Optional AWS S3 static/media storage configured in `pickem/pickem/settings.py`.
- `django-cors-headers==3.13.0` - CORS middleware and whitelist configured in `pickem/pickem/settings.py`.
- `django-ratelimit==4.1.0` - Installed and configured, but app installation/decorators are disabled in `pickem/pickem/settings.py` and `pickem/pickem_homepage/views.py`.
- `APScheduler==3.9.1` and `django-apscheduler==0.6.2` - Scheduling dependencies present in `pickem/requirements.txt`; active Kubernetes cron scheduling is defined in `charts/family-pickem/templates/cronjob.yaml`.
- `Pillow==9.0.1` - Image processing dependency available for profile/avatar/media workflows.
- `beautifulsoup4==4.11.1` - HTML parsing dependency present in `pickem/requirements.txt`.
- `django-crispy-forms==1.14.0`, `django-tables2==2.4.1`, `django-bootstrap-v5==1.0.11` - Template/form/table frontend helpers available to Django views/templates.

## Configuration

**Environment:**
- Django requires `SECRET_KEY` in `pickem/pickem/settings.py`.
- Database selection in `pickem/pickem/settings.py` uses `RDS_DB_NAME`/`RDS_USERNAME`/`RDS_PASSWORD`/`RDS_HOSTNAME`/`RDS_PORT` for AWS RDS-style deployments, `DATABASE_HOST`/`DATABASE_NAME`/`DATABASE_USER`/`DATABASE_PASS`/`DATABASE_PORT` for standard deployments, or a default Docker PostgreSQL host `postgresql:5432`.
- Host and CSRF configuration uses `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `THIS_POD_IP` in `pickem/pickem/settings.py`.
- Optional S3 storage is enabled by `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` in `pickem/pickem/settings.py`.
- Cron API authentication uses optional `API_TOKEN` in `pickem/pickem_api/cron.sh`, passed as `--token` to scripts such as `pickem/pickem_api/cron_update_games_v2.py`.
- Legacy RapidAPI integration uses `X_RAPIDAPI_KEY` only in `pickem/pickem_api/cron_update_games.py`; the active `cron.sh` path calls `cron_update_games_v2.py`.
- Docker Compose expects an env file `.env.app` in `docker-compose.yml`; no `.env*` file is present at repo root.

**Build:**
- `package.json` defines Tailwind build scripts and dev dependencies.
- `tailwind.config.js` scans `pickem/pickem_homepage/templates/**/*.html` and `pickem/pickem_homepage/**/*.py`, uses class-based dark mode, and defines project colors/fonts/shadows.
- `docker/app/Dockerfile` copies `pickem/`, installs `pickem/requirements.txt`, exposes port `8000`, and delegates startup to `docker/app/docker-entrypoint.sh`.
- `docker-compose.yml` runs Bitnami PostgreSQL 15 and the Django container.
- `charts/family-pickem/Chart.yaml` defines a Helm application chart with Bitnami PostgreSQL dependency `12.5.6`.

## Platform Requirements

**Development:**
- Python 3.10 with dependencies from `pickem/requirements.txt`.
- PostgreSQL available at the configured host; Docker development uses `docker.io/bitnami/postgresql:15` from `docker-compose.yml`.
- Node/npm for Tailwind builds using `npm run build:css` or `npm run build:prod`.
- Required runtime env includes `SECRET_KEY` and database variables unless using the Docker fallback database settings in `pickem/pickem/settings.py`.

**Production:**
- Docker image `familypickem/pickem-django` is produced by GitHub Actions in `.github/workflows/publish-artifacts.yaml`.
- Kubernetes deployment is described by Helm chart `charts/family-pickem/` with optional Bitnami PostgreSQL, External Secrets, CronJob, ingress, probes, and autoscaling.
- Optional AWS S3 static/media storage is configured in `pickem/pickem/settings.py`.
- Optional S3 PostgreSQL backups are defined in `charts/family-pickem/templates/backup-cronjob.yaml`.
- ArgoCD production target revision is updated by `.github/workflows/publish-artifacts.yaml` under `infra/argocd/applications/pickem-prd.yaml`.

---

*Stack analysis: 2026-06-28*
