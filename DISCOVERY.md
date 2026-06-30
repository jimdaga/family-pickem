# Discovery: Family Multi-Tenancy

**Date:** 2026-06-28  
**Scope:** Discovery only for evolving Family Pickem from one global league into isolated family/pool tenancy.

## Current Architecture

Family Pickem is a Django monolith with two main apps:

- `pickem_api`: domain models, DRF serializers, JSON endpoints, and cron data-sync scripts.
- `pickem_homepage`: template-rendered browser pages, forms, profile settings, message board, commissioner dashboard, and static assets.

The main request paths are:

- Browser routes mount from `pickem/pickem/urls.py` to `pickem/pickem_homepage/urls.py`.
- API routes mount under `/api/` to `pickem/pickem_api/urls.py`.
- Scheduled jobs in `pickem/pickem_api/cron_*.py` call the app's HTTP API rather than using management commands and ORM transactions directly.

## Tech Stack

| Area | Current state |
|---|---|
| Framework | Django 4.0.2, Django REST Framework 3.13.1 |
| UI | Django templates, Tailwind CSS 3.4.18, Bootstrap dependency still present during migration |
| Auth | Django sessions plus django-allauth Google OAuth |
| ORM/database | Django ORM, PostgreSQL in dev/prod, SQLite in test settings |
| Background jobs | Standalone Python cron scripts plus Kubernetes CronJob/Helm templates |
| Static/media | Django staticfiles, optional S3 via `django-storages` |
| Tests | Django test runner, `pickem.test_settings` |
| CSS build | `npm run build:css`, `npm run build:prod` |
| CI/CD | GitHub Actions release workflow runs Django tests, builds Docker image, publishes Helm chart, updates ArgoCD prod target |
| Deployment | Docker, Helm, Kubernetes, ArgoCD, optional PostgreSQL chart dependency |

Useful commands:

```bash
cd pickem && python manage.py test --settings=pickem.test_settings
npm run build:prod
cd pickem && python manage.py check --settings=pickem.test_settings
```

## Current Domain Model

Core models in `pickem/pickem_api/models.py`:

- `UserProfile`: one-to-one with Django `User`; stores tagline, favorite team, phone, notification/theme/privacy settings, and global `is_commissioner`.
- `Teams`: NFL team rows by season.
- `GamesAndScores`: NFL game rows, including week, season, scores, status, odds, weather, venue, broadcast, and gamecast data.
- `GameWeeks`: week/date/season mapping.
- `GamePicks`: user picks stored with denormalized user fields (`userEmail`, `uid`, `userID`) plus game identifiers, season, week, pick, tiebreaker values, and correctness.
- `userSeasonPoints` and legacy `userPoints`: one row per user/season with denormalized `week_1_*` through `week_18_*` scoring fields.
- `userStats`: denormalized per-user season/all-time stat fields.
- `currentSeason`: global current season singleton in practice, but no uniqueness constraint.

Community models in `pickem/pickem_homepage/models.py`:

- `SiteBanner`: global active site banner.
- `MessageBoardPost`, `MessageBoardComment`, `MessageBoardVote`: global league discussion and voting.

Current global/single-family assumptions:

- There is no `family_id`, `pool_id`, membership, invite, tenant setting, or tenant-scoped role model.
- `UserProfile.is_commissioner` is a global privilege.
- Standings are global by `gameseason`.
- Picks are global by `gameseason`, `gameWeek`, `competition`, `uid`, and `userEmail`.
- Message-board posts/comments/votes are global.
- Site banners are global.
- User profile pages and stats are global, with only a private-profile boolean.
- Footer stats context queries global standings and picks for the current user.
- Cron scoring updates all global picks and standings for a season/week.
- API reads expose global games, weeks, teams, picks, user points, and current season.
- URLs do not carry a tenant context.

## Current Pages, Routes, And APIs

Public/browser routes:

- `/`: homepage/dashboard with global standings preview, league stats, picks status, and message board.
- `/scores/`: current week scores and global pick stats.
- `/scores/competition/<competition>/season/<season>/week/<week>`: historical scores.
- `/standings/`: global leaderboard by selected season.
- `/rules/`: global rules page.
- `/picks/`: visible to anonymous users with auth-required state; accepts POST today.
- `/user/<user_id>/`: public user profile unless profile is private.
- `/message-board/comments/<post_id>/`: public comment JSON endpoint.

Authenticated/browser routes:

- `/profile/`: current user's profile/settings.
- `/picks/edit/`: edit current user's pick.
- `/check-username/`: AJAX username availability.
- `/toggle-theme/`: AJAX profile theme setting.
- `/message-board/create-post/`, `/create-comment/`, `/vote-post/`, `/vote-comment/`: message board mutations.

Commissioner routes:

- `/commissioners/`
- `/commissioners/set-week-winner/`
- `/commissioners/manage-banner/`
- `/commissioners/deactivate-banner/`
- `/commissioners/submit-manual-pick/`
- `/commissioners/get-user-picks/`

API routes:

- `/api/currentseason`
- `/api/games`, `/api/games/<id>`
- `/api/weeks`, `/api/weeks/<date>`
- `/api/userinfo/<id>`
- `/api/userpickids/<season>/<week>`
- `/api/picks/<game_id>`
- `/api/userpicks/<pick_id>`
- `/api/userpicks/<season>/<week>/<uid>`
- `/api/teams/`, `/api/teams/id/<team_id>`
- `/api/activegames/`, `/api/unscored`
- `/api/userpoints/`, `/api/userpoints/add`, `/api/userpoints/<season>/<id>`, `/api/userpointsdel/<season>/<id>`

Current data-fetching patterns:

- Function-based views query ORM models directly.
- Templates receive already-aggregated querysets and dictionaries.
- DRF function views parse JSON manually and use serializers directly.
- Cron scripts call API endpoints per game/user/pick.
- No service/repository layer centralizes authorization or tenant scoping.

## Security Findings

Authentication boundaries:

- Page authentication uses `@login_required` on selected routes only.
- API default permission is `IsAuthenticated`, but many views override with `AllowAny` or `IsAdminOrReadOnly`, making reads public.
- Google OAuth is configured through allauth.

Authorization boundaries:

- Commissioner access is global (`UserProfile.is_commissioner` or `User.is_superuser`).
- Pick edit checks `GamePicks.id` plus `userEmail=request.user.email`.
- Most read paths have no ownership or membership check because the product is global.
- Message-board reads and profile reads are global.

IDOR/BOLA and cross-family leakage risks for the future model:

- `/user/<user_id>/` would expose another family member or non-member's stats unless scoped.
- `/api/picks/<game_id>`, `/api/userpickids/<season>/<week>`, and `/api/userpicks/<season>/<week>/<uid>` would expose picks across families.
- `/api/userpoints/<season>/<id>` and standings pages would expose season totals across families.
- Commissioner manual pick and week-winner endpoints accept user/game/week/season identifiers without tenant membership checks.
- Message board endpoints fetch by post/comment ID only.
- Site banners are global and would leak admin communication across families.
- Footer context processors globally query current user's rank and correct-pick counts.
- Pick creation uses `GamePicksForm` with many client-controlled fields that should be server-derived.

Other security concerns:

- Several authenticated JSON endpoints use `@csrf_exempt`.
- Error responses often return raw exception text.
- `DEBUG` is hardcoded to `'True'`, which also disables rate limiting.
- `SOCIALACCOUNT_LOGIN_ON_GET=True`.
- Rate limiting is installed but disabled.
- `currentSeason` is treated as a singleton without a database constraint.
- `MessageBoardVote` allows both post and comment nullable targets; it lacks a check constraint requiring exactly one target.
- API delete-all endpoints exist for games and weeks behind staff-only write permissions.
- Dependencies are pinned to older versions and need a security upgrade plan.
- Secret-management manifests exist under `infra/`; secret scanning should be part of hardening.

## UX Findings

Current journeys:

- Unauthenticated visitors land on a polished public homepage with Google sign-in, public scores, standings, rules, and a visible picks page with auth-required messaging.
- Signed-in users land on the global homepage, can submit picks, view standings, scores, profiles, and message board.
- Commissioners see a nav entry and dashboard if they have global commissioner privileges.

Gaps for multi-family UX:

- No onboarding state for "signed in but not in a family."
- No family creation or join flow.
- No invite link/code flow.
- No family switcher or visible current-family context.
- URLs do not show family/pool context, so users cannot tell where they are.
- The navigation and copy use global "league" language.
- Empty states are mostly generic or absent.
- Commissioner tools are global and would be confusing/unsafe for family admins.
- Mobile nav has no place for family switcher or current family indicator.
- Public profile and message board behavior needs a clear product decision: family-private by default is safest.

Professional polish opportunities:

- Add first-run onboarding after Google sign-in.
- Add a compact header family switcher with current family name.
- Make `/families/<slug>/...` or `/pools/<slug>/...` URLs unambiguous.
- Replace global "Family League" wording with tenant-aware copy.
- Add consistent 403/404 behavior that avoids leaking family existence.
- Add role-aware settings/member/invite pages.
- Replace fake/sample profile chart data with an empty state.

## Migration Risks

Existing production data should be mapped into a default legacy family and pool.

High-risk tables:

- `GamePicks`: must receive a pool/tenant boundary without changing pick IDs unexpectedly.
- `userSeasonPoints`, `userPoints`, `userStats`: precomputed global standings/stats must become pool-scoped.
- `MessageBoardPost`, `MessageBoardComment`, `MessageBoardVote`: must become family/pool-scoped.
- `UserProfile.is_commissioner`: global commissioner roles must map to owner/admin membership in the legacy family.
- `SiteBanner`: decide whether banners remain site-wide or become family-scoped.

Migration risks:

- Adding non-null foreign keys directly can lock tables or fail on existing rows.
- Backfilling denormalized records by email/user ID may encounter missing/deleted users.
- Duplicate records may violate new unique constraints once tenant keys are added.
- Cron jobs may write unscoped data during a rolling deployment if code and schema are not staged.
- Cached/precomputed standings may mix scoped and unscoped calculations during rollout.
- Reversibility is limited after moving to tenant-scoped data unless a snapshot backup exists.

## Questions That Do Not Block Discovery But Should Be Answered Before Build

- Should games/weeks/teams remain global NFL reference data while picks/standings are pool-scoped? Recommendation: yes.
- Should message boards belong to `Family` or `Pool`? Recommendation: start with family-level discussion unless pool-specific threads are required.
- Should public standings exist at all? Recommendation: no for family pools unless a family setting explicitly permits public viewing.
- Should users see profiles of members in other shared families? Recommendation: only inside a shared family context.
- Should a family be able to run multiple simultaneous pools? Recommendation: schema should support it, even if UI starts with one active pool.
