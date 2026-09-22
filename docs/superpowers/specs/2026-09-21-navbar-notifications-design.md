# Navbar Notifications — Design

**Date:** 2026-09-21
**Status:** Approved, ready for implementation plan

## Goal

Add an in-app notifications system to the top navbar: a bell icon with an
unread-count badge and a dropdown panel listing recent notifications. To make
room, remove the user's display name from the user-dropdown trigger.

This change is **scaffolding only**. It puts the database model, the context
plumbing, and the UI in place. Nothing in the codebase creates notifications
yet; producers land in follow-up work.

## Scope

**In scope**
- `Notification` model + migration
- Context processor supplying the unread count and recent items
- Desktop navbar bell + badge + dropdown panel
- Mobile navbar bell + badge + in-menu notifications section
- Removal of the display name from the user-dropdown trigger
- Mark-all-read and per-item open/mark-read views
- Tests for all of the above

**Explicitly out of scope**
- Any producer that creates `Notification` rows
- A `/notifications/` full-history page
- SSE / live push of new notifications (the existing Redis SSE infrastructure
  in `pickem_homepage/live_views.py` can be layered on later)
- Email delivery (the existing `email_notifications` profile flag is unrelated
  and untouched)

## Data model

New model `Notification` in `pickem/pickem_api/models.py`. It lives in
`pickem_api` rather than `pickem_homepage` because `UserProfile`, `Family`, and
`Pool` are defined there, keeping every foreign key local to the app.

| Field | Type | Notes |
|---|---|---|
| `recipient` | `ForeignKey(User, on_delete=CASCADE, related_name='notifications')` | |
| `kind` | `CharField(max_length=32, choices=Kind.choices)` | see Kinds below |
| `title` | `CharField(max_length=200)` | the bold line in the panel |
| `body` | `CharField(max_length=500, blank=True, default='')` | optional supporting line |
| `url` | `CharField(max_length=500, blank=True, default='')` | already-resolved path |
| `family` | `ForeignKey(Family, null=True, blank=True, on_delete=SET_NULL)` | pool-scoped items only |
| `pool` | `ForeignKey(Pool, null=True, blank=True, on_delete=SET_NULL)` | pool-scoped items only |
| `read_at` | `DateTimeField(null=True, blank=True)` | null means unread |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

**Why `url` stores a resolved path** rather than a route name plus kwargs: this
app is multi-tenant, so almost every member-facing route needs
`(family_slug, pool_slug)`. The producer already holds that context when it
creates the row; storing the finished path keeps the template dumb and avoids a
reverse() that can raise `NoReverseMatch` during a navbar render on every page.

**Why `read_at` is a nullable timestamp** rather than an `is_read` boolean: it
answers "is it read" (`read_at__isnull`) and "when was it read" with one field,
at no extra cost.

**Meta**
- `ordering = ['-created_at']`
- Index on `(recipient, read_at, created_at DESC)`, which covers both the badge
  count query and the recent-items query.

**Kinds** — `Notification.Kind`, a `models.TextChoices`:

| Value | Label | Icon (Font Awesome) |
|---|---|---|
| `picks_open` | Picks open | `fa-clipboard-list` |
| `picks_missed` | Missed picks | `fa-triangle-exclamation` |
| `week_winner` | Week winner | `fa-trophy` |
| `season_winner` | Season winner | `fa-crown` |
| `message_reply` | Message reply | `fa-comment-dots` |
| `family_invite` | Family invite | `fa-ticket` |
| `announcement` | Announcement | `fa-bullhorn` |

The kind-to-icon map is a module-level dict exposed through a
`Notification.icon` property, so the template renders `{{ n.icon }}` with no
`{% if %}` ladder. Adding a kind later is a choices edit plus a migration for
the choices change only — no schema change.

**Manager** — `NotificationQuerySet` / `Notification.objects`:
- `unread_for(user)` — unread rows for a user
- `recent_for(user, limit=10)` — newest `limit` rows, `select_related('pool')`

## Context processor

`notifications_context(request)` in `pickem/context_processors.py`, registered
in `settings.py` `TEMPLATES['OPTIONS']['context_processors']` after the
existing entries.

Provides:
- `notification_unread_count` — integer
- `notification_items` — list of the 10 most recent notifications (read and
  unread alike; unread ones are styled differently in the panel)

Behaviour:
- Anonymous requests short-circuit to `{'notification_unread_count': 0,
  'notification_items': []}` with zero queries.
- The whole body is wrapped in `try/except Exception` returning those same
  defaults, matching the defensive pattern already used by `theme_context`. A
  context processor that raises breaks every page on the site, so it must
  degrade rather than propagate.

Cost: two queries per authenticated page render (one count, one list). The
badge renders `9+` for counts above 9, but the count query is not capped — a
future optimisation can cache it per user.

## UI — desktop navbar

In `pickem/pickem_homepage/templates/pickem/base.html`, inside the
authenticated right-hand cluster, a new bell block is inserted immediately
**before** the existing user-profile dropdown (currently at line ~182).

It reuses the existing `.dropdown-container` / `.dropdown-trigger` /
`.nav-dropdown` structure, so the existing `toggleDropdown()` handler, the
click-outside-to-close handler, and the "close all other dropdowns" behaviour
all apply with no new JavaScript.

- **Trigger**: `<button>` with `fa-bell`, `aria-label="Notifications"`, styled
  to match the neighbouring bordered pill buttons. Carries
  `data-testid="notifications-bell"`.
- **Badge**: absolutely positioned pill on the bell, red background, white bold
  text, `data-testid="notifications-badge"`. Rendered only when
  `notification_unread_count` is non-zero.
- **Panel**: `w-80`, same surface/border/shadow tokens as the user dropdown.
  - Header row: "Notifications" plus a **Mark all read** submit button (a POST
    form, shown only when there is at least one unread).
  - Items: each an `<a>` to the per-item open view, showing the kind icon, the
    title, the body, and `{{ n.created_at|timesince }} ago`. Unread items get a
    tinted background and a left accent bar.
  - Empty state: "You're all caught up."

## UI — user dropdown trimming

Remove the `<span class="text-white font-medium">{{ user|display_name }}</span>`
from the user-dropdown trigger. The avatar, the rank pip
(`data-testid="navbar-rank"`), and the chevron stay. The display name remains
in the dropdown's own header row, so the information is one click away.

No existing test asserts the display name inside the trigger, so nothing
breaks. A new regression test pins the removal.

## UI — mobile

- A bell button with the same badge sits next to the hamburger toggle in the
  mobile header, visible only below `lg`, carrying
  `data-testid="notifications-bell-mobile"`.
- Inside `#mobile-menu`, a "Notifications" section using the existing
  `mobile-dropdown-container` / `toggleMobileDropdown()` pattern, listing the
  same `notification_items` and offering the same mark-all-read form.
- Tapping the mobile bell opens `#mobile-menu` and expands that section. This
  is the one piece of new JavaScript in the change: a click handler that
  unhides `#mobile-menu` (the same class toggle `#mobile-menu-btn` performs)
  and then calls the existing `toggleMobileDropdown()` on the notifications
  trigger when it is still collapsed. Everything else reuses handlers already
  in `base.html`.

## Views and URLs

Both views live in `pickem_homepage/views.py` and are registered in the
project URLconf.

**`POST /notifications/mark-read/`** → `notifications_mark_all_read`
- `@login_required`, POST only (`@require_POST`), CSRF-protected by default.
- Stamps `read_at = timezone.now()` on the requester's unread rows.
- Redirects to `request.META.get('HTTP_REFERER')` when it passes
  `url_has_allowed_host_and_scheme(..., allowed_hosts={request.get_host()})`,
  otherwise to `index`. Never redirects to an unvalidated referer.

**`GET /notifications/<int:notification_id>/go/`** → `notification_open`
- `@login_required`.
- `get_object_or_404(Notification, pk=..., recipient=request.user)` — a
  notification belonging to another user is a 404, not a 403, so the endpoint
  does not confirm the row exists.
- Stamps `read_at` if unread, then redirects to the notification's `url`, or to
  `index` when `url` is blank.
- The stored `url` is validated with `url_has_allowed_host_and_scheme` before
  redirecting, so a bad producer cannot turn a notification into an open
  redirect.

This pair is why panel items are links rather than JS: per-item read works with
no client-side code.

## Testing

**`pickem/pickem_api/tests/test_notifications.py`** (new file)
- Defaults: a freshly created notification is unread (`read_at is None`).
- Ordering: `Notification.objects.all()` returns newest first.
- `unread_for(user)` excludes read rows and other users' rows.
- `recent_for(user, limit)` honours the limit and the ordering.
- `icon` returns the mapped Font Awesome class for each kind.

**`pickem/pickem_homepage/tests.py`** (appended)
- Context processor: correct unread count and items for an authenticated user;
  zeroes for an anonymous request; other users' notifications never leak.
- Navbar: bell and badge render when unread exist; badge absent at zero; badge
  shows `9+` above nine.
- Navbar regression: the user-dropdown trigger no longer contains the display
  name.
- `notifications_mark_all_read`: requires login, rejects GET, marks only the
  requester's rows, redirects to a same-host referer and ignores a foreign one.
- `notification_open`: marks read and redirects to the stored url; 404s on
  another user's notification; redirects to index when url is blank; refuses a
  foreign-host url.

## Build and deployment notes

- The new markup introduces Tailwind utility classes, so `npm run build:prod`
  must run and the rebuilt `pickem/pickem_homepage/static/css/tailwind.css`
  must be committed — the compiled stylesheet is served directly.
- Never append a `?v=...` cache-buster to a `{% static %}` URL (see CLAUDE.md).
- One migration, additive only (a new table). No backfill, no data migration,
  safe to apply while the app is serving.
