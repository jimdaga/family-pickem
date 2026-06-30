# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Family Pickem is a Django-based NFL pick'em league web application where users predict game winners and compete on a leaderboard. The app features Google OAuth authentication, real-time game updates, comprehensive statistics tracking, and a message board for league discussion.

**Current Status**: Undergoing migration from Bootstrap 5 to Tailwind CSS (see TAILWIND_MIGRATION_PLAN.md)

## Development Environment

### Local Development Server
- **Webserver runs at**: `http://localhost:8000`
- **Assumption**: The server is already running when making changes
- **Validation**: Use `curl http://localhost:8000` to inspect HTML output and validate changes
- **Important**: When making CSS changes, consider JavaScript interactions with the DOM - the final appearance may depend on JS execution

### Starting the Development Server
```bash
# From project root
cd /Users/jim/git/family-pickem && source venv/bin/activate && cd pickem && python manage.py runserver

# Or step by step:
source venv/bin/activate
cd pickem
python manage.py runserver
```

### Database
```bash
# Run migrations
python manage.py migrate

# Create migrations after model changes
python manage.py makemigrations

# Create superuser
python manage.py createsuperuser
```

### Tailwind CSS Build Process
```bash
# Development (watch mode)
npm run build:css

# Production (minified)
npm run build:prod
```

## Project Architecture

### Django Apps Structure

**`pickem/pickem/`** - Main project settings
- `settings.py` - Configuration, database, Google OAuth setup
- `urls.py` - Root URL routing
- `utils.py` - Shared utilities (including `get_season()`)
- `context_processors.py` - Theme and banner context for templates

**`pickem/pickem_api/`** - Core backend logic and data models
- `models.py` - Database models for games, picks, teams, user stats
- `views.py` - DRF API views
- `serializers.py` - DRF serializers
- `admin.py` - Django admin configuration
- `cron_*.py` - Automated data update scripts (see Cron Jobs section)

**`pickem/pickem_homepage/`** - Frontend views and templates
- `views.py` - Template views for all user-facing pages
- `forms.py` - Django forms for picks, message board
- `models.py` - Message board models (posts, comments, votes)
- `templates/pickem/` - HTML templates
- `static/` - CSS, JS, images
- `templatetags/` - Custom template filters/tags

### Key Database Models

**Game Data**:
- `GamesAndScores` - NFL game data including scores, timestamps, betting odds, weather
- `GameWeeks` - Week definitions and scheduling
- `Teams` - NFL team information and records

**User Picks & Stats**:
- `GamePicks` - Individual game predictions by users
- `userSeasonPoints` - Season-long point totals and weekly winners
- `userStats` - Comprehensive performance statistics (accuracy, perfect weeks, missed picks)
- `UserProfile` - Extended user settings (tagline, theme, notifications, commissioner status)

**Community**:
- `MessageBoardPost` - League discussion posts
- `MessageBoardComment` - Comments on posts
- `MessageBoardVote` - Upvotes/downvotes

### Season Management

The application uses a `YYZZ` format for seasons (e.g., "2425" for 2024-2025 season).

**Getting the current season**:
```python
from pickem.utils import get_season

# Returns int like 2425
season = get_season()

# Returns string like "24/25" for display
season_display = get_season(display_name=True)
```

Season transitions occur in April. The `get_season()` utility fetches from the API `/api/currentseason/` with fallback logic.

### Cron Jobs & Automated Updates

The app uses several Python scripts to sync with external NFL data sources:

**`cron_update_games_v2.py`** - Fetches and updates game data including:
- Scores and game status
- Betting odds (spread, over/under, win probability)
- Weather conditions and venue information
- Uses ESPN API for data

**`cron_update_picks.py`** - Scores user picks after games complete

**`cron_update_standings.py`** - Updates leaderboard and season points

**`cron_update_records.py`** - Updates team win/loss records

**`cron_add_standings.py`** - Initializes season standings for new users

These scripts accept `--url` parameter for the API endpoint (defaults to localhost).

### Authentication & Authorization

**Google OAuth**: Primary login method via django-allauth
- Configured in `settings.py` under `SOCIALACCOUNT_PROVIDERS`
- Redirects: `LOGIN_REDIRECT_URL = '/'`, `LOGOUT_REDIRECT_URL = '/'`

**Commissioner Permissions**:
```python
from pickem_homepage.views import is_commissioner, commissioner_required

# Check if user is commissioner
if is_commissioner(request.user):
    # Allow access

# Decorator for views
@commissioner_required
def admin_view(request):
    pass
```

Commissioners are identified via `UserProfile.is_commissioner` flag or `is_superuser`.

### Rate Limiting

Rate limiting is configured but **disabled in development** to avoid cache backend issues.
- Production: Uses file-based cache backend
- Configuration in `settings.py`: `RATELIMIT_ENABLE = False` when `DEBUG='True'`

## Common Development Commands

### Running Tests
```bash
cd pickem
python manage.py test
```

### Database Operations
```bash
# Shell with Django models loaded
python manage.py shell

# Database shell
python manage.py dbshell
```

### Static Files
```bash
# Collect static files for production
python manage.py collectstatic
```

### Custom Management Commands
```bash
# Create superuser (automated)
python manage.py createsu

# Manage site banners
python manage.py manage_banners
```

### Docker Development
```bash
# Start all services (PostgreSQL + Django)
docker-compose up

# Build and start
docker-compose up --build

# Stop services
docker-compose down

# View logs
docker-compose logs -f django
```

Database runs on `postgresql:5432` within Docker network.

### Cron Job Execution (Manual)
```bash
cd pickem/pickem_api

# Update games for current week
python cron_update_games_v2.py --url localhost

# Update specific week
python cron_update_games_v2.py --url localhost --gameweek 5

# Update user picks
python cron_update_picks.py --url localhost

# Update standings
python cron_update_standings.py --url localhost
```

## Important Notes from claude_instructions.md

When applying changes:

1. **Webserver is running** at `http://localhost:8000` - don't start it yourself
2. **Use curl** to fetch and inspect output: `curl http://localhost:8000`
3. **Parse HTML responses** to validate changes
4. **Consider JavaScript interactions** when making CSS changes - DOM may be dynamically modified
5. **Don't assume static HTML** - JS may apply classes, styles, or state changes

## Configuration

### Environment Variables

Required for development (typically in `.env.app`):
- `SECRET_KEY` - Django secret key
- `DATABASE_*` - PostgreSQL connection details
- `GOOGLE_OAUTH2_KEY` - Google OAuth client ID
- `GOOGLE_OAUTH2_SECRET` - Google OAuth client secret

Optional:
- `DJANGO_ALLOWED_HOSTS` - Comma-separated hosts
- `CSRF_TRUSTED_ORIGINS` - Trusted origins for CSRF
- `AWS_STORAGE_BUCKET_NAME` - S3 bucket for static files (production)
- `DEBUG` - Enable debug mode

### Current Season Configuration

The current season is managed via the database model `CurrentSeason`. Use the API endpoint or `get_season()` utility rather than hardcoding season values.

## Dependencies

Key packages:
- **Django 4.0.2** - Web framework
- **djangorestframework** - API endpoints
- **django-allauth** - Google OAuth
- **psycopg2-binary** - PostgreSQL driver
- **django-bootstrap-v5** - Bootstrap integration (being phased out)
- **espn-api** - NFL data integration
- **boto3/django-storages** - AWS S3 for static files (production)
- **django-ratelimit** - Rate limiting (production)
- **Tailwind CSS** - Modern CSS framework (in migration)

See `requirements.txt` for complete list.

## Tailwind CSS Migration

The project is actively migrating from Bootstrap 5 to Tailwind CSS. See `TAILWIND_MIGRATION_PLAN.md` for:
- Detailed migration phases
- Component conversion patterns
- Color/typography tokens
- Dark mode implementation strategy

**Current state**: Tailwind is installed and configured, base infrastructure is ready, templates are being converted incrementally.

## URL Patterns

Key routes (see `pickem/urls.py` and `pickem_homepage/views.py`):
- `/` - Homepage with standings preview
- `/picks/` - Weekly pick submission
- `/standings/` - Full leaderboard
- `/scores/` - Live game scores
- `/stats/` - Player statistics
- `/profile/<userid>/` - User profiles
- `/rules/` - League rules
- `/api/` - DRF API endpoints
- `/admin/` - Django admin panel

## Code Style Notes

- Use Django ORM for database queries (avoid raw SQL)
- Follow Django naming conventions (models: `CamelCase`, views/functions: `snake_case`)
- Template files use Django template language with Bootstrap/Tailwind classes
- API views use Django REST Framework serializers and viewsets
- Custom template tags in `pickem_homepage/templatetags/`

## Testing & Debugging

Access the Django admin at `/admin/` after creating a superuser. Use Django Debug Toolbar in development for query analysis (if installed).

For template debugging, check:
- Context processors in `settings.py`
- Template inheritance from `base.html`
- Static file loading with `{% load static %}`

## Deployment

### ArgoCD GitOps (Production Infrastructure)

The application runs on a single-node Kubernetes 1.28 cluster (`dagabuntu.home` / `192.168.1.222`) managed by ArgoCD. All infrastructure is GitOps-managed:

**Environments:**
- **Production (`pickem-prd`)**: Runs the latest GitHub Release. Deployed automatically when a release is published.
- **Dev (`pickem-dev`)**: Runs the latest code from `main`. Deployed automatically on every push to main.

**Deployment flow — DO NOT hardcode chart versions:**
- **Dev**: ArgoCD uses `targetRevision: ">=0.0.0-latest"` to auto-track every new `-latest` chart published on push to main. No manual version updates needed.
- **Prd**: The `update_argocd` job in `publish-artifacts.yaml` automatically updates `pickem-prd.yaml`'s `targetRevision` when a GitHub Release is published. Never manually edit the prd targetRevision.

**Key files:**
- `infra/argocd/applications/` — ArgoCD Application manifests (prd, dev, argocd self-mgmt, ESO, nginx)
- `infra/app/values-prd.yaml` / `values-dev.yaml` — Helm values per environment
- `charts/family-pickem/` — Helm chart templates
- `.github/workflows/publish-artifacts.yaml` — Release workflow (Docker + Helm + ArgoCD prd update)
- `.github/workflows/publish-artifacts-latest.yaml` — Main branch workflow (Docker + Helm `-latest`)

**Secrets**: Managed via External Secrets Operator (ESO) pulling from AWS Secrets Manager (`family-pickem/{prd,dev}/{envvars,pickemctl}`)

**CRITICAL — Secrets workflow:**
- **NEVER manually edit K8s secrets** — ESO will overwrite them on the next sync (every 1h or on annotation change). Always update the source of truth in AWS Secrets Manager.
- **AWS CLI auth required** — If the AWS session is expired, ask the user to run `aws login` before making any secret changes. Do not attempt secret operations with an expired session.
- After updating AWS Secrets Manager, force ESO sync: `kubectl annotate externalsecret <name> -n <ns> force-sync=$(date +%s) --overwrite`
- Then restart the deployment to pick up new values: `kubectl rollout restart deployment/<name> -n <ns>`

**Known quirks:**
- Bitnami PostgreSQL subchart names services as `{release}-postgresql`, NOT `{fullnameOverride}-postgresql`
- ESO pinned to v0.19.2 (K8s 1.28 compat — v1.x+ needs K8s 1.30+)
- TLS terminated at Cloudflare edge, no cert-manager on cluster
- This dev machine (fedora) is NOT the K8s node — use `ssh jim@192.168.1.222` for node ops

### Legacy Reference
- AWS S3 for static file storage
- PostgreSQL database (self-hosted on K8s via Bitnami subchart)
- Docker images published to Docker Hub (`familypickem/pickem-django`)
- Environment-based configuration (see `settings.py` for RDS/K8s detection)
