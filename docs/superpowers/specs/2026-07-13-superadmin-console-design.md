# Superadmin Console Design

## Goal

Give site superusers a cross-family operator console at `/superadmin/` for the work Django admin and the per-family admin hub both do badly: seeing and editing settings across *all* families at once, blocking users site-wide, repairing broken data, and running the update pipeline on demand.

Django admin (`/admin/`) stays as the raw-CRUD escape hatch. This console does not replace it.

## Why Not Django Admin

Django admin already registers CRUD for every model, and superusers already reach every family's admin hub via god-mode in `authz.py`. Neither of those gives you:

- One table showing the same setting across every pool (today: click into each family, one at a time).
- A site-wide user block (today: only `User.is_active`, a bare boolean with no reason, no actor, no timestamp).
- Guarded data-repair actions (today: Django shell).
- On-demand pipeline runs (today: wait for the scheduler, or shell in).
- A health view of the scheduler (today: notice the scores are stale).

## Access Control

A single decorator, `@superadmin_required`, in `pickem_superadmin/decorators.py`:

- Requires `request.user.is_superuser`. Not `is_staff`. Not `UserProfile.is_commissioner` — a commissioner governs one family; this console is global.
- Returns **404**, not 403, for everyone else, so the URL does not confirm the console exists to a probing non-admin.
- Applied to every view and every POST handler in the app. The app has no undecorated view by construction, and a test asserts this across every registered URL.

All writes are POST + CSRF. Destructive writes additionally require a typed confirmation (see Data Repair).

`is_superuser` itself is **not editable from this console**. Promoting a superuser from a web UI is a privilege-escalation surface; that stays in Django admin / shell.

## Architecture

New Django app, `pickem_superadmin`, mounted at `/superadmin/`:

```
pickem/pickem_superadmin/
  urls.py            /superadmin/...
  decorators.py      @superadmin_required
  views/
    overview.py
    families.py
    pools.py         settings matrix
    users.py         block/unblock
    teams.py
    jobs.py
    audit.py
  forms.py
  services.py        data-repair actions (no HTTP awareness)
  templates/superadmin/
    base.html        standalone; extends nothing from the site
  tests/
```

Rationale: `pickem_homepage/views.py` is already ~3,700 lines, and mixing global-scoped auth into a module full of tenant-scoped auth is how you end up with a view that forgot its gate. Isolating a security-sensitive surface makes it auditable in one place.

`services.py` holds the repair actions as plain functions with no request/HTTP awareness, so they are directly unit-testable and reusable from a shell.

## Look and Feel

Deliberately not on-brand. `templates/superadmin/base.html` extends nothing from the site: no navbar, no family switcher, no theme toggle, no brand colors.

- Neutral grays, ~13px system-ui, monospace for IDs / seasons / counts.
- Tight table rows, minimal rounding, high density.
- Thin top bar: section nav + "← back to site".
- Built with the existing Tailwind pipeline (no new CSS dependency or build step).

New Tailwind utility classes require `npm run build:prod` and committing `tailwind.css`.

## Data Model Changes

### 1. `SuperAdminAuditLog` (new model)

`FamilyAuditLog.family` is a non-null FK, so it structurally cannot record a global action ("blocked user X", "changed team colors", "rolled the current season").

Rejected alternative: making `FamilyAuditLog.family` nullable. That reuses one table but forces every existing family-audit reader to handle a null family, and pollutes a family's own history with global noise.

Chosen: a separate table.

| Field | Type | Notes |
| --- | --- | --- |
| `actor` | FK User, `SET_NULL` | who did it |
| `action` | TextChoices | e.g. `user_blocked`, `pool_settings_updated`, `job_queued` |
| `target_type` | CharField | e.g. `Pool`, `User` |
| `target_id` | CharField | |
| `summary` | CharField | short human string |
| `changes` | JSONField | `{field: [before, after]}` |
| `ip_address` | GenericIPAddressField | |
| `user_agent` | TextField | |
| `created_at` | DateTimeField | |

Every write in the console goes through one `log_action()` helper, so writing without logging is not possible.

**Dual-write rule:** when an action is family-scoped and a commissioner should also see it (e.g. a superadmin edits a pool's settings), write **both** a `SuperAdminAuditLog` row and the existing `FamilyAuditLog` row, so the family's own history has no mysterious gaps.

Because `changes` captures before/after, the Audit page doubles as forensics for a bad edit.

### 2. `UserProfile` block fields

There is no site-wide block today — only `User.is_active` (no reason, no actor, no timestamp) and `FamilyMembership.status` (per-family removal).

Add to `UserProfile`: `blocked_at` (DateTimeField, null), `blocked_by` (FK User, `SET_NULL`, null), `blocked_reason` (TextField, blank).

Block semantics:

- Sets `User.is_active = False` **and** stamps the three fields. `is_active=False` blocks Django login for free.
- Flushes the user's existing sessions (delete `django_session` rows whose decoded `_auth_user_id` matches), so the block takes effect immediately rather than at next login.
- Unblock reverses both halves and logs.
- **Guards:** a superuser cannot be blocked; you cannot block yourself.

## Pages

Seven sections. The matrix pattern — dense table, inline-editable cells, one "Save changes" that diffs and writes only what changed — repeats across Pools, Teams, and Users.

### 1. Overview

A health board, not a decorative dashboard.

- **Counts:** families (active/inactive), pools, users (active/blocked), picks this week.
- **Scheduler health:** is a scheduler alive; last `update_all` execution + status; last `update_records`; a loud red banner if the last run failed or nothing has run in >5 minutes. Today the pipeline dying is only discoverable by noticing stale scores.
- **Anomaly checks** — cheap queries, each linking to the thing that fixes it:
  - pools with no `PoolSettings` row
  - games stuck `in progress` past a plausible end time
  - users with picks but no `userSeasonPoints` row
  - families with zero active members
  - pools whose season ≠ `currentSeason`
  - unscored completed games
- **Site settings panel:** `currentSeason` (season + `display_name` — this drives `get_season()` across the whole app and is currently a bare Django admin row), and site-wide `SiteBanner` publishing (the model already supports a null `family` = global banner).

### 2. Families

Every family in one table: name, slug, status, `logo_url`, member count, pool count, created. Inline-editable name / slug / `logo_url` / status. Deactivating is the soft "turn this off" lever. Rows link to that family's pools and members.

### 3. Pools — the settings matrix

Rows = every pool across every family. Columns = all 16 `PoolSettings` fields plus the pool's own `name` / `season` / `status` / `is_default`.

- Sticky first column (family/pool) and sticky header, so it stays readable through horizontal scroll.
- Filter by family / season / status.
- Editable cells; one Save.

Editable settings: `win_points`, `tie_points`, `weekly_winner_points`, `picks_lock_at_kickoff`, `allow_tiebreaker`, `primary_tiebreaker`, `secondary_tiebreaker`, `perfect_week_bonus_enabled`, `perfect_week_bonus_amount`, `entry_fee_enabled`, `entry_fee_amount`, `missed_pick_policy`, `late_join_policy`, `payout_structure`.

**`pick_type=against_spread` and `include_playoffs` stay locked, even here.** They are not gated by permission — they are gated by the code not existing (playoff scoring needs schema work; `userSeasonPoints` only has `week_1..18` columns, and every pipeline command hardcodes `range(1, 19)`). Letting a superadmin flip them would not enable a feature, it would silently corrupt scoring. They render visibly disabled with a "not implemented" tooltip, **and the server rejects them** — the widget is never trusted. When the backend lands, unlock them in both this form and `FamilyAdminSettingsForm`.

### 4. Users

Global user table: username, email, joined, last login, families, blocked status.

Actions:
- **Block / unblock** (typed confirmation + required reason; semantics above).
- Toggle `UserProfile.is_commissioner`.
- Edit the `UserProfile` fields that go wrong in practice: `favorite_team`, `tagline`, `private_profile`, `email_notifications`.

Not here: `is_superuser` (see Access Control).

### 5. Teams

Closes the open TODO item ("Add `Teams.logo_contrast_preset` editing to the future superadmin page").

All 32 teams: `logo_contrast_preset`, `color`, alt color, plus a **live preview swatch rendering the actual branded tile** next to each row, so contrast fixes are seen rather than guessed from hex codes. Also team records / `gameseason`, for when ESPN drifts.

### 6. Jobs

Moves the existing superuser-only job-runs page out of the family hub, where it never belonged — the scheduler is system-wide, yet the page is currently reachable only by first picking an arbitrary family.

- Registered jobs (`DjangoJob`).
- Execution history (`DjangoJobExecution`): status, duration, exception.
- **Queue-run** button per pipeline command: `update_all`, `update_games`, `update_picks`, `update_standings`, `update_stats`, `update_records`, `update_weekly_winners`, `update_season_winners`, `update_missed_picks`, `update_rankings`.

### 7. Audit

Global `SuperAdminAuditLog`: who, what, before→after, when, from where. Filterable by actor and action.

Plus a read-only combined stream of every family's `FamilyAuditLog`, which today can only be read one family at a time.

## Job Execution

Clicking "queue run" does **not** run the command in the web request. `update_games` makes ESPN calls and `update_all` chains the whole pipeline — either could outlive a gunicorn worker timeout, and a browser refresh would fire it twice.

Instead the view enqueues a one-off APScheduler job into the existing `DjangoJobStore`:

```python
scheduler.add_job(run_command, 'date', run_date=now,
                  id=f'manual:{cmd}:{timestamp}', args=[cmd])
```

The jobstore is the database, so the web worker only writes a row. The scheduler process (the one with `RUN_SCHEDULER=true`) picks it up on its next wakeup and executes it. `update_all` already runs every minute, so that wakeup is ≤60s away. Execution lands in `DjangoJobExecution` automatically — run history needs no new tracking code.

**The tradeoff is real and must be shown, not hidden:** the job is *enqueued*, not instant. The button reads "Queue run", and the row shows `queued → running → finished/failed` rather than pretending it ran synchronously.

**Failure mode this creates:** if no scheduler process is alive, queued jobs pile up in the jobstore and never run, silently. Mitigations:
- Overview leads with scheduler health.
- The Jobs page refuses to queue, with a clear explanation, when it cannot see a recent execution from a live scheduler.
- `max_instances=1` on the pipeline jobs already prevents a manual run colliding with the scheduled one.

## Data Repair

Plain functions in `services.py`. Each maps to a real breakage:

| Action | Purpose | Idempotent |
| --- | --- | --- |
| Recompute pool standings/stats | re-run scoring scoped to one pool | yes |
| Re-score a week | clear + recompute `pick_correct` and points for one pool/week after a corrected result | yes |
| Fix a stuck game | edit `GamesAndScores` status/scores when ESPN wedges a game in-progress | n/a |
| Delete a bogus pick | remove a `GamePicks` row (duplicate, cancelled game) | no |
| Reset a user's season row | rebuild a drifted `userSeasonPoints` row | no |
| Backfill missing `PoolSettings` | create the default row for a pool with none (linked from the Overview anomaly) | yes |

Every one is destructive by nature, so each:

- Requires a **typed confirmation** — type the pool slug or username to arm the button. Not a checkbox, not an "are you sure" dialog.
- Captures **before/after into `SuperAdminAuditLog.changes`**.
- Runs inside a transaction.

The recompute-style actions are idempotent by construction. The delete/reset ones are not — which is precisely why the audit log stores what was there before.

## Error Handling

- **Repair failures** roll back the transaction and surface the real error to the operator. This is a superuser-gated admin console, not a public page — a real exception message is a feature, and it matches the existing job-runs page, which already shows tracebacks to superusers.
- **Matrix saves** validate per-cell and re-render the table with bad cells flagged and good edits preserved, rather than dropping the whole submission.
- **Concurrent edits:** matrix forms carry each row's `updated_at`. If it changed underneath you, the save is rejected with "this row changed since you loaded it" instead of clobbering.

## Testing

`pickem_superadmin/tests/`, following the existing suite: `cd pickem && python manage.py test --settings=pickem.test_settings` (SQLite in-memory).

- **Authorization, parameterized across every registered URL in the app:** anonymous → 404, ordinary member → 404, family commissioner → 404, superuser → 200. A new view with a missing decorator fails the suite. This is the test that keeps the console from becoming a hole.
- **Blocking:** sets `is_active=False`, stamps profile fields, flushes sessions; cannot block a superuser; cannot block yourself; unblock reverses.
- **Locked fields:** a hand-crafted POST setting `pick_type=against_spread` or `include_playoffs=True` is rejected server-side, not merely disabled in the widget.
- **Matrix save:** writes only changed cells; a stale `updated_at` is rejected; one invalid cell does not discard the valid ones.
- **Audit:** every write path produces a `SuperAdminAuditLog` row with correct before/after.
- **Repair services:** unit-tested directly against fixtures; idempotency asserted on the recompute paths.

## Out of Scope

- **Impersonation / view-as-user.** Explicitly rejected: it is a session-hijack primitive, and without it every action stays attributable to the superadmin rather than laundered through a user's session.
- **Replacing Django admin.** `/admin/` remains for raw CRUD.
- **Editing `is_superuser`.**
- **Enabling against-the-spread or playoffs.** Those are backend features, not permissions; this console must not pretend otherwise.
