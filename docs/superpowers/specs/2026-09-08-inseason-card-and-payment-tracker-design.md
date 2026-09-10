# In-season commissioner card + payment tracker

**Date:** 2026-09-08

## Feature 1 — In-season commissioner card

### Problem

The lobby's commissioner card only exists before the season's first kickoff
(shipped 0.0.209). Once the season starts a commissioner has no quick route to
the things they actually do week to week.

### Design

Replace the lobby view's boolean `show_commissioner_setup` with a single
`commissioner_card` context value: `'preseason'`, `'inseason'`, or `''`. Exactly
one card can render, and mutual exclusivity is structural rather than two
booleans that have to agree.

| Phase | When | Links |
| --- | --- | --- |
| `preseason` | commissioner **and** `now < season_kickoff` | Invite players, Pool settings, Post a lobby note |
| `inseason` | commissioner **and** `now >= season_kickoff` | Post a lobby note, Pool settings, Members |
| `''` | not a commissioner | — |

"Commissioner" stays `role_allows(membership.role, ADMIN)`, and the kickoff
boundary stays the earliest `startTimestamp` for the pool's season and
competition — both unchanged from 0.0.209.

The in-season card reuses `.commissioner-message-card`, with the heading
"Running your pool" and no "disappears at kickoff" subtitle, since it persists
for the rest of the season.

Deliberately **not** included: the picks and weekly-winners admin links, and the
payments page. Scope is the three links above.

## Feature 2 — Payment tracker

### Problem

`PoolSettings` already carries `entry_fee_enabled` and `entry_fee_amount`, but
nothing records who has actually paid. Commissioners track it out of band.

### Opt-in

`PoolSettings.payment_tracking_enabled`, `BooleanField(default=False)`, added to
`PoolRulesForm` so the commissioner enables it from their own Pool Settings
page. While off: no admin page content, no lobby notice, nothing written.

Defaulting off is a hard requirement — no existing player should suddenly be
told they owe money because a feature shipped.

### Model

`PoolMemberPayment`

| Field | Notes |
| --- | --- |
| `pool` | FK, `PROTECT` (matches `GamePicks`; payment history must not vanish with a pool) |
| `user` | FK |
| `gameseason` | int, YYZZ — status is per season |
| `paid` | bool |
| `note` | short free text, blank allowed |
| `marked_by` | FK to User, `SET_NULL`, for accountability |
| `marked_at` | when the flag last changed |
| `created_at` / `updated_at` | bookkeeping |

Unique on `(pool, user, gameseason)`.

**Absence of a row means unpaid.** Enabling the feature therefore requires no
backfill, and nothing is written until a commissioner marks someone.

### Admin page

`/families/<family>/pools/<pool>/admin/payments/`, gated at
`minimum_role=ADMIN` — deliberately not owner-only, so an admin can manage
payments without also getting member management (which is owner-only).

Lists active members with a paid checkbox and note, showing who marked each and
when, plus a summary: paid count and total collected against
`entry_fee_amount`.

With the toggle off the page renders an explanatory "off" state linking to Pool
Settings rather than 404ing — a commissioner who follows a stale link should
learn why it is empty.

Writes are audited through `FamilyAuditLog` with a new `PAYMENT_UPDATED` action.

### Lobby notice

When the toggle is on and the viewer has no `paid=True` row for this pool and
season, the lobby shows a quiet inline notice near the top:

> Entry fee outstanding — see your commissioner.

It includes the amount when `entry_fee_amount` is set. It is informational: it
blocks nothing, gates nothing, and is not an error. Commissioners see it too if
they have not paid.

## Accepted consequence

The first time a commissioner enables the toggle, every member reads as unpaid
until marked. That follows from absence-means-unpaid and is the reason the
feature is opt-in per pool.

## Tests

- `payment_tracking_enabled` defaults to False; lobby notice and page content
  are absent while off.
- Payments page gate: a plain member gets 403 on both GET and POST; admin
  and owner reach it.
- Marking paid writes the row, sets `marked_by`/`marked_at`, and writes a
  `FamilyAuditLog` row; unmarking clears `paid`.
- Lobby notice shows for an unpaid member only when the toggle is on, and
  disappears once marked paid.
- Notice is scoped to the pool and season — a paid row in another pool or
  season does not suppress it.
- Commissioner card: preseason before kickoff, inseason after, neither for a
  plain member; the in-season card links to lobby notes, settings and members
  and does **not** contain the invite link.
- Render/require parity for `PoolRulesForm` on the admin settings template
  (the bug class from PR #175).

## Migrations

Two migrations:

- `0098` — the new `PoolMemberPayment` model, the `PoolSettings` field, and the
  `FamilyAuditLog.Action` choice addition.
- `0099` — replaces the `family_audit_log_action_valid` CHECK constraint. The
  allowed-action list is hardcoded in the model `Meta`, so the enum choice alone
  does not reach the database; without this every payment write fails with
  `CHECK constraint failed`.
