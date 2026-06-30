# External Integrations

**Analysis Date:** 2026-06-28

## APIs & External Services

**NFL Data:**
- ESPN site scoreboard API - Active game schedule, score, status, odds, weather, venue, broadcast, and gamecast data sync.
  - SDK/Client: `requests` in `pickem/pickem_api/cron_update_games_v2.py`.
  - Auth: Not required.
- ESPN site teams API - Team list, colors, and display metadata.
  - SDK/Client: `requests` in `pickem/pickem_api/cron_update_records.py`.
  - Auth: Not required.
- ESPN core sports API - Team details, logos, and season records.
  - SDK/Client: `requests` in `pickem/pickem_api/cron_update_records.py`.
  - Auth: Not required.
- ESPN Python package - Imported as `from espn_api.football import League` in `pickem/pickem_api/cron_update_games_v2.py`.
  - SDK/Client: `espn-api==0.45.1`.
  - Auth: Not detected in active usage.
- ViperScore via RapidAPI - Legacy scheduled-game fetch path in `pickem/pickem_api/cron_update_games.py`; not called by active `pickem/pickem_api/cron.sh`.
  - SDK/Client: `requests`.
  - Auth: `X_RAPIDAPI_KEY`.

**Internal API Consumers:**
- Cron update scripts - `pickem/pickem_api/cron_update_games_v2.py`, `pickem/pickem_api/cron_update_picks.py`, `pickem/pickem_api/cron_update_records.py`, `pickem/pickem_api/cron_update_standings.py`, `pickem/pickem_api/cron_update_rankings.py`, and `pickem/pickem_api/cron_add_standings.py` call the app's own `/api/` endpoints over HTTP.
  - SDK/Client: `requests`.
  - Auth: Optional DRF token passed as `API_TOKEN` through `pickem/pickem_api/cron.sh` and `--token` arguments.

**Frontend CDNs and Browser Services:**
- Google Tag Manager / Google Analytics - Global tracking script in `pickem/pickem_homepage/templates/pickem/base.html`.
  - SDK/Client: Browser script from `https://www.googletagmanager.com/gtag/js`.
  - Auth: Measurement ID embedded in template; no server secret detected.
- Bootstrap CDN - CSS and JS loaded in `pickem/pickem_homepage/templates/pickem/base.html`.
  - SDK/Client: jsDelivr Bootstrap 5.0.0 CSS and Bootstrap 5.0.1 JS.
  - Auth: Not required.
- Popper CDN - Bootstrap dependency loaded in `pickem/pickem_homepage/templates/pickem/base.html`.
  - SDK/Client: jsDelivr `@popperjs/core@2.9.2`.
  - Auth: Not required.
- Font Awesome CDN - Icons loaded in `pickem/pickem_homepage/templates/pickem/base.html`.
  - SDK/Client: cdnjs Font Awesome 6.0.0.
  - Auth: Not required.
- Google Fonts - `Inter` and `Urbanist` loaded in `pickem/pickem_homepage/templates/pickem/base.html`.
  - SDK/Client: Browser CSS from `fonts.googleapis.com` and `fonts.gstatic.com`.
  - Auth: Not required.
- Alpine.js CDN - Page-level interactivity loaded in `pickem/pickem_homepage/templates/pickem/standings.html` and `pickem/pickem_homepage/templates/pickem/scores.html`.
  - SDK/Client: jsDelivr `alpinejs@3.x.x`.
  - Auth: Not required.
- Chart.js CDN - User profile charts loaded in `pickem/pickem_homepage/templates/pickem/user_profile.html`.
  - SDK/Client: jsDelivr `chart.js` and `chartjs-plugin-datalabels@2`.
  - Auth: Not required.
- WMATA icon URL - Default avatar fallback image used in views and templates including `pickem/pickem_homepage/views.py`, `pickem/pickem_homepage/templates/pickem/home.html`, and `pickem/pickem_homepage/templates/pickem/scores.html`.
  - SDK/Client: Browser image URL.
  - Auth: Not required.

**Cloud Metadata:**
- AWS EC2 instance metadata - Local private IP added to allowed hosts when `RDS_DB_NAME` exists.
  - SDK/Client: `requests.get('http://169.254.169.254/latest/meta-data/local-ipv4')` in `pickem/pickem/settings.py`.
  - Auth: Instance metadata endpoint; no app secret.

## Data Storage

**Databases:**
- PostgreSQL - Primary application database configured in `pickem/pickem/settings.py`.
  - Connection: `RDS_DB_NAME`, `RDS_USERNAME`, `RDS_PASSWORD`, `RDS_HOSTNAME`, `RDS_PORT`; or `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASS`, `DATABASE_HOST`, `DATABASE_PORT`; or Docker defaults `pickem`/`postgresql:5432`.
  - Client: Django ORM with `django.db.backends.postgresql_psycopg2` and `psycopg2-binary==2.9.3`.
- Bitnami PostgreSQL - Local and chart-managed database option.
  - Connection: `docker-compose.yml` service `postgresql`; Helm dependency in `charts/family-pickem/Chart.yaml`.
  - Client: Django ORM.
- SQLite - Test-only database in `pickem/pickem/test_settings.py`.
  - Connection: local test database.
  - Client: Django ORM.

**File Storage:**
- Local static/media filesystem by default.
  - Implementation: `STATIC_ROOT` under `pickem/pickem/static` in `pickem/pickem/settings.py`.
- AWS S3 optional storage.
  - Implementation: `storages.backends.s3boto3.S3Boto3Storage` enabled in `pickem/pickem/settings.py` when `AWS_STORAGE_BUCKET_NAME` exists.
  - Auth: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_REGION_NAME`.
- AWS S3 optional database backups.
  - Implementation: `aws s3 cp`, `aws s3 ls`, and `aws s3 rm` in `charts/family-pickem/templates/backup-cronjob.yaml`.
  - Auth: Kubernetes secret keys `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_DEFAULT_REGION`.

**Caching:**
- Django file-based cache.
  - Implementation: `django.core.cache.backends.filebased.FileBasedCache` at `/tmp/django_cache` in `pickem/pickem/settings.py`.
  - Used for: Rate-limit cache when rate limiting is enabled.
- Redis is not active.
  - Evidence: Redis service is commented out in `docker-compose.yml`; requirements comments mention `redis` and `django-redis` as future production options.

## Authentication & Identity

**Auth Provider:**
- Google OAuth through django-allauth.
  - Implementation: `allauth.socialaccount.providers.google` in `pickem/pickem/settings.py`; login links use `{% provider_login_url 'google' %}` in templates such as `pickem/pickem_homepage/templates/pickem/base.html` and `pickem/pickem_homepage/templates/pickem/home.html`.
  - Auth: Google OAuth app credentials managed by allauth provider configuration; environment names are documented as `GOOGLE_OAUTH2_KEY` and `GOOGLE_OAUTH2_SECRET` in project instructions, but direct reads are not present in `pickem/pickem/settings.py`.
- Django session authentication.
  - Implementation: `django.contrib.auth.backends.ModelBackend`, session middleware, and DRF `SessionAuthentication` in `pickem/pickem/settings.py`.
- DRF token authentication.
  - Implementation: `rest_framework.authtoken` app and `TokenAuthentication` in `pickem/pickem/settings.py`.
  - Auth: Cron scripts accept `--token`; `pickem/pickem_api/cron.sh` reads optional `API_TOKEN`.

## Monitoring & Observability

**Error Tracking:**
- Not detected. No Sentry, Rollbar, Honeybadger, or equivalent dependency/configuration found in `pickem/requirements.txt`, `pickem/pickem/settings.py`, or `.github/workflows/`.

**Logs:**
- Django and cron scripts use stdout/stderr.
- Cron scripts print status and payload diagnostics in files such as `pickem/pickem_api/cron_update_games_v2.py`, `pickem/pickem_api/cron_update_picks.py`, and `pickem/pickem_api/cron_update_records.py`.
- Kubernetes captures app and CronJob logs from containers defined in `charts/family-pickem/templates/deployment.yaml` and `charts/family-pickem/templates/cronjob.yaml`.

## CI/CD & Deployment

**Hosting:**
- Docker image target: `familypickem/pickem-django` in `charts/family-pickem/values.yaml` and `.github/workflows/publish-artifacts.yaml`.
- Kubernetes/Helm: Chart in `charts/family-pickem/` deploys the Django app, service, ingress, HPA, CronJob, secrets, optional External Secrets, and optional backups.
- Docker Compose: Local deployment in `docker-compose.yml` with Django plus PostgreSQL.
- ArgoCD: Production app revision update references `infra/argocd/applications/pickem-prd.yaml` in `.github/workflows/publish-artifacts.yaml`.

**CI Pipeline:**
- GitHub Actions release pipeline.
  - Tests: `run_tests` job installs `pickem/requirements.txt` and runs Django tests in `.github/workflows/publish-artifacts.yaml`.
  - Docker publish: `publish_docker` builds `docker/app/Dockerfile` and pushes to Docker Hub.
  - Helm publish: `publish_helm` updates `charts/family-pickem/Chart.yaml` and runs chart-releaser.
  - ArgoCD update: `update_argocd` commits target revision changes for production.

## Environment Configuration

**Required env vars:**
- `SECRET_KEY` - Required by `pickem/pickem/settings.py`.
- Database variables - `DATABASE_HOST`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASS`, `DATABASE_PORT` for standard deployments, or `RDS_DB_NAME`, `RDS_USERNAME`, `RDS_PASSWORD`, `RDS_HOSTNAME`, `RDS_PORT` for RDS-style deployments.
- `DJANGO_ALLOWED_HOSTS` - Required for non-local hostnames in `pickem/pickem/settings.py`.
- `CSRF_TRUSTED_ORIGINS` - Required for non-local trusted origins in `pickem/pickem/settings.py`.
- `GOOGLE_OAUTH2_KEY`, `GOOGLE_OAUTH2_SECRET` - Required for Google OAuth per project instructions and django-allauth social app configuration.

**Optional env vars:**
- `THIS_POD_IP` - Added to allowed hosts in Kubernetes by `charts/family-pickem/templates/deployment.yaml`.
- `DEBUG` - Checked for rate-limit enablement in `pickem/pickem/settings.py`; `DEBUG` itself is currently hardcoded to `'True'`.
- `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - Enable S3 storage in `pickem/pickem/settings.py`.
- `AWS_DEFAULT_REGION` - Used by the backup CronJob in `charts/family-pickem/templates/backup-cronjob.yaml`.
- `API_TOKEN` - Optional DRF token for cron scripts in `pickem/pickem_api/cron.sh`.
- `X_RAPIDAPI_KEY` - Legacy RapidAPI key for `pickem/pickem_api/cron_update_games.py`.

**Secrets location:**
- Local Docker: `.env.app` referenced by `docker-compose.yml`; file not present in repo.
- Helm inline secret: `charts/family-pickem/templates/secret.yaml` converts `.Values.app.env` into a Kubernetes Secret when External Secrets are disabled.
- External Secrets Operator: `charts/family-pickem/templates/external-secret-envvars.yaml` extracts secret data from `.Values.externalSecrets.envvarsKey` in a `ClusterSecretStore`.
- GitHub Actions: Docker Hub and GitHub tokens use GitHub Secrets in `.github/workflows/publish-artifacts.yaml`.

## Webhooks & Callbacks

**Incoming:**
- Third-party webhook endpoints: None detected.
- OAuth callbacks: django-allauth handles Google OAuth callback routes under `/accounts/` through allauth URL configuration; provider login links are in `pickem/pickem_homepage/templates/pickem/base.html` and `pickem/pickem_homepage/templates/pickem/home.html`.
- Browser AJAX endpoints: Internal POST endpoints for picks, theme toggles, profile updates, message board actions, and commissioner actions are implemented in `pickem/pickem_homepage/views.py` and called from templates such as `pickem/pickem_homepage/templates/pickem/picks.html`, `pickem/pickem_homepage/templates/pickem/profile.html`, and `pickem/pickem_homepage/templates/pickem/home.html`.

**Outgoing:**
- ESPN data fetches from cron scripts to `site.api.espn.com` and `sports.core.api.espn.com` in `pickem/pickem_api/cron_update_games_v2.py` and `pickem/pickem_api/cron_update_records.py`.
- Legacy RapidAPI data fetches to `viperscore.p.rapidapi.com` in `pickem/pickem_api/cron_update_games.py`.
- App-internal HTTP updates from cron scripts to `/api/` endpoints through the host passed as `--url`.
- Browser asset fetches to Google, jsDelivr, cdnjs, Google Fonts, and WMATA icon URLs from Django templates.
- Optional AWS S3 API calls for static/media storage through django-storages and for backups through `charts/family-pickem/templates/backup-cronjob.yaml`.

---

*Integration audit: 2026-06-28*
