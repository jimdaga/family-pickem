## Family Pickem – Architectural Review and Improvement Roadmap

A focused, actionable plan to improve maintainability, performance, UX, and feature depth for the NFL pick’em platform.

### Executive summary
The app shows a strong foundation (Django/DRF, Helm/ArgoCD assets, responsive templates). Biggest wins will come from:
- Centralizing “season/week” and pick-lock logic
- Normalizing per-week scoring storage and adding constraints
- Converting cron scripts into managed background tasks with caching
- Modularizing frontend JS/templates, polishing mobile UX and accessibility
- Adding observability, tests, and consistent API semantics/versioning

The sections below provide detailed recommendations and a prioritized implementation plan.

## High-level priorities
- Centralize current season and week logic; make it reusable and tested
- Normalize weekly points storage; add uniqueness constraints
- Convert cron scripts to resilient background jobs; add caching for scores/leaderboards
- Migrate inline page scripts to static JS modules; extract repeated template components
- Add CI (pre-commit linters/tests) and basic observability

## Architecture & code quality

### Season/week and lock logic (DRY)
- Consolidate logic into `pickem/utils.py`:
  - get_current_season()
  - get_current_week(today=None, season=None) with preseason=>week 1 fallback
  - are_picks_locked_for_week(week)
- Replace ad-hoc fallbacks across `pickem_homepage/views.py`, `pickem_api/views.py`, and cron scripts.
- Add unit tests for edge cases (preseason, bye weeks, holiday schedules).

### API structure and semantics
- Move resources to DRF ViewSets (Games, Weeks, Picks) with routers.
- Introduce API versioning (`/api/v1/...`) and consistent error payloads.
- Ensure read/write permissions; rate-limit write endpoints.

### Data modeling and integrity
- Replace “wide” weekly fields with a normalized table:
  - `UserWeekPoints(user, season, week, points, bonus, winner)` with unique `(user, season, week)`
- Materialize seasonal aggregates (e.g., `UserSeasonAgg`) nightly for fast leaderboards.
- Add DB constraints and indexes:
  - `GamesAndScores`: indexes on `(gameseason, competition, gameWeek)`, `slug`, `startTimestamp`
  - `GameWeeks`: unique `(season, weekNumber)`, index `date`
  - `GamePicks`: unique `(uid, pick_game_id)`
- Migrate to timezone-aware datetimes (store UTC; render user/local TZ).

### Error handling and consistency
- Replace bare `except:` with targeted exceptions; return DRF error responses.
- Standardize preseason=>week 1 behavior across all code paths.

## Backend operations & performance

### Background jobs
- Convert cron Python scripts to:
  - Django management commands, or
  - Celery tasks (preferred) with Redis (broker/cache)
- Add idempotent upserts and structured logging with correlation IDs.
- Schedule with Celery beat or Kubernetes CronJobs that call management commands.

### Caching strategy
- Cache week leaderboards and scores fragments (15–30s TTL during live windows).
- Cache season aggregates and team standings (longer TTL).
- Invalidate selectively after scoring updates.

### Observability
- JSON logs with request/job IDs, durations, and cardinality-safe labels.
- Basic metrics: API latency/throughput, task success/failure, queue depths.
- Health checks and readiness probes.

## Frontend & UX

### Scores page (polish and performance)
- Keep “full-width time groups” with rounded container/square header bottom.
- Make filter bar sticky; add “scroll to top” on long lists.
- Live updates: minimize DOM thrash by updating only changed nodes; consider SSE/WebSockets later.

### Accessibility and responsiveness
- Ensure WCAG contrast in light/dark modes.
- Keyboard and ARIA for collapsible headers; maintain focus states.
- Verify mobile tap targets (≥44px), avoid horizontal scrolling, lazy-load long lists.

### Template/JS organization
- Move inline scripts to static modules (`static/js/scores.js`, `picks.js`).
- Extract reusable components:
  - Game card, pick badge, leaderboard row (Django inclusion tags or partials).

## Gameplay features (engagement)

- Confidence points (optional weekly mode)
- Survivor side game
- Reminders (email/SMS) before locks; notify weekly winners
- Social/league spaces (custom scoring/branding)
- Insights: trend charts, team bias, contrarian pick, “swing games”
- Onboarding walkthrough for new users

## Security

- Enforce CSRF on AJAX posts consistently; auth required for picks/edit.
- Add throttling to mutating endpoints.
- Secrets via Kubernetes Secrets; no secrets in repo.

## Deployment & infra

- Pre-deploy migrations job; rollback strategy.
- Readiness/liveness probes for app and workers.
- Serve static assets via CDN/NGINX with cache-busting.

## Data lifecycle

- Season partitioning/tags; “season switcher” across pages.
- Safe backfills/replays to rescore weeks if upstream changes.

## Documentation

- Developer docs: architecture diagram, models overview, lock windows, season/week resolution.
- Operator runbooks: rescore week, reprocess jobs, rotate secrets, restore backups.

---

## Implementation plan (phased)

### Phase 1 — Correctness and foundations (1–2 weeks)
- Centralize season/week/lock utilities; update all call sites.
- Add DB constraints and key indexes; migration for normalized `UserWeekPoints`.
- Introduce pre-commit: black, isort, ruff/flake8; basic CI.

### Phase 2 — Jobs and performance (1–2 weeks)
- Convert cron scripts to management commands or Celery tasks.
- Implement caching (Redis) for scores/leaderboards; invalidate on updates.
- Structured logging and simple metrics.

### Phase 3 — UX modularization and accessibility (1–2 weeks)
- Extract page JS to modules; componentize templates.
- Add sticky filter, diff-only live updates, lazy-load long lists.
- Accessibility pass (contrast, focus, ARIA), dark mode polish.

### Phase 4 — Engagement features (ongoing)
- Confidence points and survivor modes.
- Reminders/notifications; weekly winner highlights.
- Insights and charts; personal stats page enhancements.

---

## Quick wins checklist

- [ ] Utility: `get_current_week()` with preseason=>week 1 fallback
- [ ] Unique `(uid, pick_game_id)` on `GamePicks`
- [ ] Index `(gameseason, competition, gameWeek)` on `GamesAndScores`
- [ ] Cache week leaderboard (short TTL) and season aggregates
- [ ] Move inline `<script>` from `scores.html`/`picks.html` to static JS
- [ ] Sticky filters + “Back to top” button on scores page
- [ ] Replace bare `except:` blocks with targeted handling
- [ ] Add DRF API versioning (`/api/v1`) and consistent error schema

## Pointers to current code of interest

- `pickem/pickem_homepage/views.py`: current week/picks/scores pages logic
- `pickem/pickem_api/views.py`: API endpoints (weeks, games, picks)
- `pickem/pickem_api/models.py`: `GameWeeks`, `GamesAndScores`, weekly stats models
- `pickem/pickem_homepage/templates/pickem/*.html`: page templates
- `pickem/utils.py`: place to centralize season/week/lock logic
- `charts/family-pickem/`: Helm chart for deployment

---

Maintaining momentum on these priorities will reduce complexity and improve correctness under load while delivering a more polished, scalable experience for league members.