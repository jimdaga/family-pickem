# Codebase Concerns

**Analysis Date:** 2026-06-28

## Tech Debt

**Production settings are not separated from development defaults:**
- Issue: `pickem/pickem/settings.py` hardcodes `DEBUG='True'`, includes a fixed ngrok host in `ALLOWED_HOSTS`, includes fixed CSRF trusted origins, and toggles rate limiting from the string debug value.
- Files: `pickem/pickem/settings.py:30`, `pickem/pickem/settings.py:33`, `pickem/pickem/settings.py:53`, `pickem/pickem/settings.py:107`
- Impact: Production safety depends on editing code or setting compensating environment values. Debug pages, disabled rate limiting, and stale host/origin entries can leak internals or weaken request protection.
- Fix approach: Split settings into environment-specific modules or normalize `DEBUG = os.getenv("DEBUG", "False") == "True"` and make hosts, CSRF origins, secure cookie flags, and rate limiting entirely environment-driven.

**Homepage view module owns too many responsibilities:**
- Issue: `pickem/pickem_homepage/views.py` is 1,847 lines and mixes page rendering, profile updates, pick editing, message-board APIs, commissioner workflows, banner management, chart-data construction, and scoring helper logic.
- Files: `pickem/pickem_homepage/views.py:57`, `pickem/pickem_homepage/views.py:796`, `pickem/pickem_homepage/views.py:1214`, `pickem/pickem_homepage/views.py:1489`, `pickem/pickem_homepage/views.py:1724`
- Impact: Small frontend or workflow changes require editing a broad, high-conflict file. Error handling and validation patterns diverge between features.
- Fix approach: Split by feature into modules such as `pickem_homepage/views/home.py`, `pickem_homepage/views/picks.py`, `pickem_homepage/views/profiles.py`, `pickem_homepage/views/message_board.py`, and `pickem_homepage/views/commissioners.py`; move non-view calculations into service helpers.

**Season and NFL year values are duplicated and hardcoded:**
- Issue: Season fallback values differ across modules: `pickem.utils.get_season()` falls back to `2024`, `pickem_api.views.get_season()` falls back to `2025`, `cron_update_games_v2.py` falls back to `2526`, and cron game updates hardcode ESPN `game_year = "2025"`.
- Files: `pickem/pickem/utils.py:19`, `pickem/pickem_api/views.py:22`, `pickem/pickem_api/cron_update_games_v2.py:70`, `pickem/pickem_api/cron_update_games_v2.py:174`, `pickem/pickem_api/cron_update_records.py:79`
- Impact: New-season setup can silently query or write the wrong season. Cron jobs, API responses, and pages can disagree when the `currentSeason` row is missing or stale.
- Fix approach: Use a single season helper for Django and cron code, require a `currentSeason` row in production, and derive ESPN season years from that row instead of literals.

**Weekly scoring schema is denormalized:**
- Issue: `userSeasonPoints` and `userPoints` store `week_1_points` through `week_18_points`, bonus fields, and winner booleans as columns. Application code builds dynamic field names throughout the views and cron scripts.
- Files: `pickem/pickem_api/models.py:126`, `pickem/pickem_api/models.py:216`, `pickem/pickem_homepage/views.py:78`, `pickem/pickem_homepage/views.py:402`, `pickem/pickem_homepage/views.py:1574`, `pickem/pickem_api/cron_update_standings.py:118`
- Impact: Adding playoff weeks, alternate competitions, or scoring rules requires model migrations and dynamic attribute code changes. Queries for weekly results are harder to validate and index.
- Fix approach: Introduce a normalized `WeeklyUserResult` model keyed by user, season, competition, and week; migrate dynamic field consumers behind a repository/service layer before changing the storage shape.

**Tailwind migration leaves duplicate and mixed CSS surfaces:**
- Issue: Legacy CSS exists in both project-level and app-level static directories, while Tailwind utilities and component classes live in `input.css`. Forms still inject Bootstrap classes.
- Files: `pickem/pickem/static/css/style.css`, `pickem/pickem_homepage/static/css/style.css`, `pickem/pickem/static/css/dark-mode.css`, `pickem/pickem_homepage/static/css/dark-mode.css`, `pickem/pickem_homepage/static/css/input.css:1`, `pickem/pickem_homepage/forms.py:36`
- Impact: Visual changes can be overridden by duplicate static assets or mixed Bootstrap/Tailwind selectors. Dark-mode bugs are likely when templates, legacy CSS, and Tailwind components all define theme behavior.
- Fix approach: Keep one canonical Tailwind output path, mark legacy CSS as migration-only, remove duplicate project-level copies when unused, and convert Django form widgets to Tailwind classes with shared helper functions.

**Large templates encode complex behavior inline:**
- Issue: Core templates are very large and contain dense UI logic, inline scripts/styles, and repeated component markup.
- Files: `pickem/pickem_homepage/templates/pickem/scores.html`, `pickem/pickem_homepage/templates/pickem/home.html`, `pickem/pickem_homepage/templates/pickem/picks.html`, `pickem/pickem_homepage/templates/pickem/commissioners.html`
- Impact: Frontend changes are difficult to isolate and review. Repeated markup increases responsive and dark-mode drift.
- Fix approach: Extract repeated cards, leaderboard rows, message-board items, game cards, and profile widgets into Django partial templates under `pickem/pickem_homepage/templates/pickem/components/`.

## Known Bugs

**Team records cron script does not parse:**
- Symptoms: `python3 -m py_compile pickem/pickem_api/cron_update_records.py` fails with `SyntaxError: invalid syntax`.
- Files: `pickem/pickem_api/cron_update_records.py:32`
- Trigger: Running or importing `pickem/pickem_api/cron_update_records.py`.
- Workaround: None in the script; team records must be updated through another path or after fixing the malformed exception clause.

**Records cron uses an out-of-date fixed ESPN season year:**
- Symptoms: Team record updates query ESPN season `2025` regardless of configured `currentSeason`.
- Files: `pickem/pickem_api/cron_update_records.py:78`
- Trigger: Running `python pickem/pickem_api/cron_update_records.py --url ...` for any non-2025 season.
- Workaround: Edit the literal before running, or replace it with a derived year from `get_season()`.

**Game update cron uses an out-of-date fixed ESPN game year:**
- Symptoms: Game sync queries scoreboard `dates=2025` regardless of configured season.
- Files: `pickem/pickem_api/cron_update_games_v2.py:174`
- Trigger: Running `python pickem/pickem_api/cron_update_games_v2.py --url ...` after the 2025 NFL season.
- Workaround: Pass the desired week but the year still comes from the literal; update the literal or derive it from the current season.

**Public profile chart shows sample data when a user has no picks:**
- Symptoms: A profile with zero picks returns fake team percentages and placeholder teams instead of an empty state.
- Files: `pickem/pickem_homepage/views.py:1061`
- Trigger: Viewing `/user/<id>/` for a user with no `GamePicks` in the current season.
- Workaround: None in the view; templates receive sample chart arrays.

**Duplicate `rules` view definition shadows an earlier definition:**
- Symptoms: `rules()` is defined twice in the same module, and the later function is the one bound when `pickem_homepage.urls` imports `views.rules`.
- Files: `pickem/pickem_homepage/views.py:330`, `pickem/pickem_homepage/views.py:681`, `pickem/pickem_homepage/urls.py:12`
- Trigger: Importing `pickem_homepage.views`.
- Workaround: The later implementation renders the same page, but future edits to the earlier function have no effect.

## Security Considerations

**CSRF is disabled on authenticated JSON endpoints:**
- Risk: Authenticated users can be induced to submit state-changing JSON requests from another origin if browser and middleware conditions permit the request.
- Files: `pickem/pickem_homepage/views.py:1138`, `pickem/pickem_homepage/views.py:1175`, `pickem/pickem_homepage/views.py:1554`, `pickem/pickem_homepage/views.py:1721`
- Current mitigation: Endpoints require login or commissioner access through decorators such as `@login_required` and `@commissioner_required`.
- Recommendations: Remove `@csrf_exempt`, send CSRF tokens with AJAX requests, and add tests for 403 responses when CSRF tokens are missing.

**OAuth login starts on GET:**
- Risk: `SOCIALACCOUNT_LOGIN_ON_GET=True` starts the allauth login flow from a GET request, which reduces intentional-click friction around authentication redirects.
- Files: `pickem/pickem/settings.py:217`
- Current mitigation: Google OAuth still handles provider-side authentication and callback validation.
- Recommendations: Use POST-initiated login unless the product explicitly accepts this behavior; document the decision if retained.

**Debug and rate-limit settings are unsafe by default:**
- Risk: `DEBUG='True'` disables rate limiting and can expose detailed errors if deployed as-is.
- Files: `pickem/pickem/settings.py:30`, `pickem/pickem/settings.py:107`
- Current mitigation: Environment values can add hosts and production infrastructure can override deployment behavior outside this file.
- Recommendations: Default `DEBUG` to false, set production security headers and secure cookies, and fail deployment checks when `DEBUG` is true.

**Secrets infrastructure is present in the repo tree:**
- Risk: Secret-management manifests can accidentally expose sensitive values if inline secrets are committed.
- Files: `infra/argocd/repo-secret.yaml`, `infra/external-secrets/cluster-secret-store.yaml`
- Current mitigation: Contents were not read during this audit.
- Recommendations: Keep secret manifests encrypted or reference external secret stores only; add secret scanning in CI.

**User-facing errors expose raw exception text:**
- Risk: JSON endpoints return `str(e)` to authenticated users, which can leak model names, field names, or operational details.
- Files: `pickem/pickem_homepage/views.py:672`, `pickem/pickem_homepage/views.py:730`, `pickem/pickem_homepage/views.py:1200`, `pickem/pickem_homepage/views.py:1249`, `pickem/pickem_homepage/views.py:1313`, `pickem/pickem_homepage/views.py:1376`, `pickem/pickem_homepage/views.py:1439`, `pickem/pickem_homepage/views.py:1479`, `pickem/pickem_homepage/views.py:1618`, `pickem/pickem_homepage/views.py:1790`
- Current mitigation: Many endpoints require login or commissioner privileges.
- Recommendations: Log exception details server-side and return stable user-safe error codes/messages.

## Performance Bottlenecks

**Homepage performs many independent aggregate queries:**
- Problem: `index()` calculates standings, winners, game counts, picks counts, ranks, message-board votes, rankings, and achievements in one request path.
- Files: `pickem/pickem_homepage/views.py:57`, `pickem/pickem_homepage/views.py:72`, `pickem/pickem_homepage/views.py:107`, `pickem/pickem_homepage/views.py:121`, `pickem/pickem_homepage/views.py:136`, `pickem/pickem_homepage/views.py:196`, `pickem/pickem_homepage/views.py:244`
- Cause: Query logic lives directly in the template view with repeated model lookups and no cached read model.
- Improvement path: Add a homepage query/service object, use `select_related`/`prefetch_related` for message-board authors and votes, and cache season/week summary data.

**Public profile view performs iterative rank and team lookups:**
- Problem: `user_profile()` loops standings to compute best rank and fetches `Teams` row by row while building chart data.
- Files: `pickem/pickem_homepage/views.py:879`, `pickem/pickem_homepage/views.py:904`, `pickem/pickem_homepage/views.py:1034`, `pickem/pickem_homepage/views.py:1044`
- Cause: Derived stats are computed per request rather than stored or queried with targeted aggregates.
- Improvement path: Reuse `userStats` where possible, compute ranks with database window functions or stored ranks, and prefetch team logo data into a slug-to-team map.

**Nested comment serialization can cause recursive N+1 queries:**
- Problem: `get_post_comments()` recursively calls `comment.get_nested_replies()` and checks each user's social accounts.
- Files: `pickem/pickem_homepage/views.py:1447`, `pickem/pickem_homepage/views.py:1453`, `pickem/pickem_homepage/views.py:1456`, `pickem/pickem_homepage/views.py:1467`, `pickem/pickem_homepage/models.py:159`
- Cause: Recursive ORM access is used without prefetching the comment tree, users, or social accounts.
- Improvement path: Prefetch comments, users, and social accounts for the whole post, then build the tree in memory with a maximum nesting depth.

**Cron scripts make per-row HTTP calls back into the Django API:**
- Problem: Game updates call the local API for every game and team lookup; standings updates call user/picks endpoints per user; pick scoring calls pick and patch endpoints per game/pick.
- Files: `pickem/pickem_api/cron_update_games_v2.py:77`, `pickem/pickem_api/cron_update_games_v2.py:131`, `pickem/pickem_api/cron_update_games_v2.py:145`, `pickem/pickem_api/cron_update_picks.py:63`, `pickem/pickem_api/cron_update_standings.py:59`, `pickem/pickem_api/cron_update_standings.py:110`
- Cause: Batch jobs are external HTTP clients instead of Django management commands using ORM transactions and bulk operations.
- Improvement path: Convert cron scripts into management commands under `pickem_api/management/commands/`, use ORM reads/writes, wrap scoring in transactions, and bulk update records.

## Fragile Areas

**Pick submission trusts posted model fields:**
- Files: `pickem/pickem_homepage/forms.py:7`, `pickem/pickem_homepage/views.py:582`
- Why fragile: `GamePicksForm` exposes identifiers, user email, user IDs, game metadata, pick correctness, and season/week fields directly from POST data.
- Safe modification: Build picks server-side from `request.user` and `GamesAndScores`, expose only the selected team and tiebreaker inputs, and reject edits through `is_pick_locked()`.
- Test coverage: Existing tests smoke-test `/picks/` but do not cover forged POST data, lock rules, duplicate picks, or tiebreaker validation.

**Manual commissioner scoring uses dynamic fields without validation:**
- Files: `pickem/pickem_homepage/views.py:1554`, `pickem/pickem_homepage/views.py:1573`, `pickem/pickem_homepage/views.py:1594`
- Why fragile: `week_number` from request JSON is interpolated into field names and used for mass updates. Invalid week values become runtime field errors.
- Safe modification: Validate `week_number` as an integer in `1..18`, validate `winner_uid` against calculated candidates, and use a service function to recalculate totals.
- Test coverage: No tests cover commissioner winner selection, invalid week values, bonus recalculation, or authorization beyond anonymous redirect.

**Message-board vote counters are denormalized and race-prone:**
- Files: `pickem/pickem_homepage/models.py:97`, `pickem/pickem_homepage/models.py:192`, `pickem/pickem_homepage/models.py:209`, `pickem/pickem_homepage/views.py:1320`, `pickem/pickem_homepage/views.py:1383`
- Why fragile: Vote counts are incremented/decremented in model `save()` and `delete()` methods without `F()` expressions or transaction locks.
- Safe modification: Use atomic `F()` updates or derive counts from `MessageBoardVote` aggregates; enforce that each vote targets exactly one post or one comment.
- Test coverage: Model tests cover simple score properties but do not cover vote creation, vote changes, deletion, duplicate protection, or concurrent requests.

**Cron network calls have no timeouts and broad exception handling:**
- Files: `pickem/pickem_api/cron_update_games_v2.py:67`, `pickem/pickem_api/cron_update_games_v2.py:103`, `pickem/pickem_api/cron_update_games_v2.py:182`, `pickem/pickem_api/cron_update_picks.py:45`, `pickem/pickem_api/cron_update_standings.py:29`, `pickem/pickem_api/cron_update_records.py:57`
- Why fragile: A hung ESPN or local API request can block the job indefinitely, and broad `except:` branches hide malformed API responses by defaulting to week 1 or printing partial response data.
- Safe modification: Add explicit timeouts, response status checks, schema validation, structured logging, retries with backoff, and nonzero exits for failed jobs.
- Test coverage: Cron scripts have no unit tests around ESPN payload parsing, local API failures, fallback season logic, or scoring side effects.

**Current season lookup accepts ambiguous rows:**
- Files: `pickem/pickem/utils.py:14`, `pickem/pickem_api/views.py:22`, `pickem/pickem_api/models.py:342`
- Why fragile: `currentSeason` has no uniqueness constraint and helpers use `.first()`, `.get()`, or `.latest('id')` depending on module.
- Safe modification: Enforce a single active current-season row or make season selection explicit with an `is_active` field and a database constraint.
- Test coverage: Tests cover fallback behavior in `pickem/pickem_homepage/tests.py:123` but do not cover multiple current-season rows or API/helper consistency.

## Scaling Limits

**Season points scale by columns, not rows:**
- Current capacity: The schema supports 18 named week columns and 18 named bonus/winner columns in `userSeasonPoints`.
- Limit: Additional weeks, postseason rounds, alternate scoring periods, or multiple competitions increase schema and dynamic-field code complexity.
- Scaling path: Move weekly results into rows keyed by `(user, season, competition, week)` and keep season totals as cached aggregates.

**File-based cache backs rate limiting:**
- Current capacity: `FileBasedCache` stores up to 1,000 entries under `/tmp/django_cache`.
- Limit: Multiple containers do not share rate-limit counters, and `/tmp` cache state is ephemeral.
- Scaling path: Use Redis or another shared cache backend and enable `django-ratelimit` consistently in non-development environments.

**Homepage/message board rendering scales with comments and posts:**
- Current capacity: Homepage fetches 13 posts and comment endpoints recursively render all active nested comments for a post.
- Limit: Deep or large comment trees increase query count and response size.
- Scaling path: Paginate comments, cap nesting depth, and prefetch all needed relationships in bounded queries.

## Dependencies at Risk

**Django 4.0.2 and old pinned Python packages:**
- Risk: Core dependencies are pinned to older 2022-era versions, including `Django==4.0.2`, `djangorestframework==3.13.1`, `django-allauth==0.51.0`, `Pillow==9.0.1`, `cryptography==37.0.4`, and `requests==2.28.1`.
- Impact: Security fixes, compatibility fixes, and modern Django behavior are missing from the pinned stack.
- Migration plan: Upgrade in small groups under `pickem/requirements.txt`, run `python manage.py check`, run the Django test suite with `pickem/pickem/test_settings.py`, and address deprecations before changing application behavior.

**Bootstrap dependency remains during Tailwind migration:**
- Risk: `django-bootstrap-v5==1.0.11` and Bootstrap classes remain in forms and templates while Tailwind is also active.
- Impact: Component styling, spacing, and dark-mode behavior can diverge by page.
- Migration plan: Track remaining Bootstrap classes with `tools/css_class_scanner.py`, convert form widgets and templates incrementally, and remove the dependency only after templates no longer rely on Bootstrap classes.

**ESPN API integration lacks contract protection:**
- Risk: Cron scripts index nested ESPN response fields directly, such as scoreboard events, competitions, odds, weather, team logos, and records.
- Impact: ESPN payload changes can break imports or silently write partial game/team data.
- Migration plan: Add parser functions with fixture-based tests for representative ESPN payloads and schema guards around optional fields.

## Missing Critical Features

**No tested management-command wrapper for cron jobs:**
- Problem: Operational jobs live as standalone scripts in `pickem/pickem_api/` and call the HTTP API instead of Django internals.
- Blocks: Reliable deployment, transaction handling, app logging, test isolation, and direct use of Django settings.

**No CI-visible frontend or CSS verification command:**
- Problem: `package.json` has Tailwind build scripts but `npm test` intentionally fails.
- Blocks: Automated detection of broken templates, missing Tailwind classes, or JS-driven UI regressions.

**No centralized authorization policy for profile/message-board JSON endpoints:**
- Problem: Authorization is spread across decorators and inline ownership checks.
- Blocks: Confident changes to profile privacy, commissioner tools, message-board moderation, and AJAX endpoints.

## Test Coverage Gaps

**Pick locking, submission, and editing workflows:**
- What's not tested: Lock cutoff logic, forged pick POSTs, duplicate pick handling, tiebreakers, AJAX edit success/failure, and late-game lock behavior.
- Files: `pickem/pickem_homepage/views.py:528`, `pickem/pickem_homepage/views.py:593`, `pickem/pickem_homepage/forms.py:7`, `pickem/pickem/utils.py:54`
- Risk: Users can submit or edit incorrect picks without tests catching regressions.
- Priority: High

**Cron scoring and standings updates:**
- What's not tested: Game scoring, pick correctness updates, user season totals, new-user season row creation, and team record updates.
- Files: `pickem/pickem_api/cron_update_picks.py`, `pickem/pickem_api/cron_update_standings.py`, `pickem/pickem_api/cron_update_records.py`, `pickem/pickem_api/cron_update_games_v2.py`
- Risk: League standings can become incorrect and jobs can fail silently.
- Priority: High

**API permissions and destructive operations:**
- What's not tested: Admin-only POST/PATCH/DELETE permissions, DELETE-all endpoints, unauthenticated mutation attempts, and token-authenticated cron writes.
- Files: `pickem/pickem_api/views.py:53`, `pickem/pickem_api/views.py:80`, `pickem/pickem_api/views.py:85`, `pickem/pickem_api/views.py:140`, `pickem/pickem_api/views.py:419`
- Risk: Permission regressions can expose data mutation or deletion.
- Priority: High

**Message board and vote behavior:**
- What's not tested: Create post/comment endpoints, vote toggling, vote counter updates, duplicate votes, inactive post/comment behavior, and nested comment serialization.
- Files: `pickem/pickem_homepage/views.py:1211`, `pickem/pickem_homepage/views.py:1256`, `pickem/pickem_homepage/views.py:1320`, `pickem/pickem_homepage/views.py:1383`, `pickem/pickem_homepage/models.py:164`
- Risk: Vote counts and comment trees can drift from source votes or break under common AJAX flows.
- Priority: Medium

**Commissioner workflows:**
- What's not tested: Commissioner dashboard data, winner selection, bonus recalculation, banner management, manual pick submission, and user-pick retrieval.
- Files: `pickem/pickem_homepage/views.py:1486`, `pickem/pickem_homepage/views.py:1554`, `pickem/pickem_homepage/views.py:1625`, `pickem/pickem_homepage/views.py:1721`, `pickem/pickem_homepage/views.py:1797`
- Risk: Administrative actions can corrupt standings or expose tools to the wrong user class.
- Priority: Medium

**Frontend rendering and Tailwind migration coverage:**
- What's not tested: Responsive layout, dark mode, JS interactions, and Bootstrap-to-Tailwind regressions across the large templates.
- Files: `pickem/pickem_homepage/templates/pickem/home.html`, `pickem/pickem_homepage/templates/pickem/scores.html`, `pickem/pickem_homepage/templates/pickem/picks.html`, `pickem/pickem_homepage/templates/pickem/commissioners.html`, `pickem/pickem_homepage/static/css/input.css`
- Risk: CSS changes can break pages without a failing test.
- Priority: Medium

---

*Concerns audit: 2026-06-28*
