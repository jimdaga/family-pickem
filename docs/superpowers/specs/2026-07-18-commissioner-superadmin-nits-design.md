# Commissioner & Superadmin Nits — Design

**Date:** 2026-07-18
**Branch:** `feature/varous-nits`
**Status:** Approved design → ready for implementation plan

A batch of 10 independent fixes across the commissioner admin pages, the
superadmin console, and two public pages. Each item is self-contained and can be
implemented/tested on its own. They are grouped below by area.

---

## 1. Configurable picks-lock behavior

### Current state
- `PoolSettings.picks_lock_at_kickoff` (BooleanField, default `True`) already exists.
- `pickem/utils.py::is_pick_locked_for_pool()` already branches on it:
  `True` → lock each game at its own kickoff; `False` → `is_pick_locked()`
  (early games lock at kickoff, Sunday+ games lock together at Sunday 1PM ET).
- The **backend submit path already rejects late picks** — `render_pick_page`
  (`views.py:3401-3408`) and the edit path call `is_pick_locked_for_pool` and
  return a 400 JSON error. Multi-family submits skip locked pools individually.
- **Gap A:** the commissioner control is a checkbox labeled "Pick Locking" — not a
  clear choice.
- **Gap B (bug):** `picks.html`'s main pick-selection UI gates on
  `game.statusType != 'notstarted'` (kickoff only), so a pool set to Sunday-1PM
  does **not** visually lock Sunday-afternoon/evening games until they each start,
  even though the backend would reject the pick. Frontend and backend disagree.

### Design (decision: dropdown, default per-game kickoff, other option = Sunday 1PM ET)
Replace the boolean with an explicit mode field for clarity, superadmin display,
and future extensibility.

**Model change (`PoolSettings`):**
```python
class PicksLockMode(models.TextChoices):
    KICKOFF = 'kickoff', 'Lock each game at kickoff'
    SUNDAY_1PM = 'sunday_1pm', 'Weekly cutoff — Sunday 1PM ET'

picks_lock_mode = models.CharField(
    max_length=16, choices=PicksLockMode.choices,
    default=PicksLockMode.KICKOFF,
    help_text="When picks lock: each game at kickoff, or a weekly Sunday 1PM ET cutoff",
)
```
- **Data migration:** backfill `picks_lock_mode` from `picks_lock_at_kickoff`
  (`True` → `KICKOFF`, `False` → `SUNDAY_1PM`), then remove
  `picks_lock_at_kickoff` in the same migration set.
- Update `is_pick_locked_for_pool()` to read `settings.picks_lock_mode ==
  KICKOFF` instead of the boolean. Behavior is identical to today for existing
  data; only the storage/label changes.

**Commissioner form/UI (`PoolRulesForm`, `family_admin_settings.html`):**
- Replace the `picks_lock_at_kickoff` BooleanField with a `ChoiceField`
  (`Select` widget) named `picks_lock_mode`, using `PicksLockMode.choices`.
- Update `ADMIN_POOL_SETTINGS_FIELDS` (`views.py:1253`) and the create-family
  flow's field handling accordingly (both iterate the field list).

**Frontend fix (`picks.html`) — the important one:**
- Replace the raw `game.statusType != 'notstarted'` checks that gate the
  pick-selection cards and tiebreaker inputs with the pool-aware
  `game|is_game_locked_for_pool:pool` filter (already used lower in the same
  template for the edit/lock actions). This makes the visual lock match the
  backend rule for both modes.
- Keep the existing "already started" fallback for the logged-out/no-pool case.

**Backend graceful handling:** already implemented — no change beyond making sure
the error message reads naturally (e.g. "Picks are locked for this game").

**Superadmin visibility:** add `picks_lock_mode` as a column in the pools matrix
(`pickem_superadmin` pools page + `PoolRowForm`), read/edit alongside the other
pool settings so operators can see and correct it.

---

## 2. Late-join lockout — invite links & backend (mostly verification)

### Current state (verified)
- **Backend already blocks redemption:** `accept_invitation_for_user`
  (`views.py:671`) returns `ENTRIES_LOCKED_MESSAGE` when
  `pool_entries_locked(pool)` and the redeemer is not already an active member.
  So a stale invite link handed to a **new** person is gracefully rejected.
- The admin invites page shows a "locked" notice but **still renders the
  Create-Invite form** (intentionally, for existing members).

### Design (decision: hide the form when locked)
- In `family_admin_invites.html`, when `entries_locked` is true, **hide the
  Create-Invite section entirely** (the batch form from nit 5 included). Keep the
  amber "Entries are locked" notice and the Invite History table.
- Backend: the invite-create POST handler must also **reject creation when
  `pool_entries_locked(pool)`** (defense in depth for a stale open tab / crafted
  POST), returning a friendly error and redirecting back. This mirrors the
  redemption guard.
- No change to redemption logic — it already works. We will add/confirm a test
  that a locked pool rejects redemption of a previously-issued link.

---

## 3. Payout structure grouped under Entry Fee

### Current state
`payout_structure` renders in the generic `rule_choice_fields` loop
(`family_admin_settings.html:140`), always visible. `entry_fee_enabled`
(checkbox) + `entry_fee_amount` live in a separate card lower down.

### Design
- Remove `payout_structure` from `rule_choice_fields` (view-side grouping list).
- Render it **inside the Entry Fee card**, below the amount input.
- Show payout only when **`entry_fee_enabled` is checked AND `entry_fee_amount`
  > 0**, via a small progressive-disclosure script on the settings page
  (toggle on `change`/`input` of the two entry-fee inputs; initialize on load).
- No server-side requirement change: `payout_structure` keeps its stored value
  when hidden (harmless when no fee is collected). The field stays a valid
  choice; we simply don't surface it.

---

## 4. Banner icon → dropdown of named icons

### Current state
Two forms use a free-text `icon` TextInput: `SiteBannerForm` (superadmin banners,
on the overview page) and `FamilyBannerForm` (family admin banners page). Stored
value is a FontAwesome class string like `fas fa-bullhorn`.

### Design
- Introduce a shared curated list of ~15–20 common banner icons as
  `(value, label)` pairs, e.g.
  `('fas fa-bullhorn', 'Announcement')`, `('fas fa-trophy', 'Trophy')`,
  `('fas fa-info-circle', 'Info')`, `('fas fa-exclamation-triangle', 'Warning')`,
  `('fas fa-calendar', 'Calendar')`, `('fas fa-football-ball', 'Football')`,
  `('fas fa-star', 'Star')`, `('fas fa-fire', 'Hot')`, `('fas fa-gift', 'Gift')`,
  `('fas fa-bell', 'Bell')`, `('fas fa-check-circle', 'Success')`,
  `('fas fa-clock', 'Reminder')`, `('fas fa-users', 'Members')`,
  `('fas fa-dollar-sign', 'Money')`, `('fas fa-wrench', 'Maintenance')`.
  Defined once (e.g. module constant `BANNER_ICON_CHOICES`) and reused by both forms.
- Change the `icon` widget in **both** forms to a `Select` using those choices;
  keep the stored value as the FA class string (no model change).
- Backward-compat: if an existing banner's stored icon isn't in the list, prepend
  its current value as a selectable option so editing doesn't silently change it.
- Small enhancement: render a live icon preview next to the dropdown (a
  `<i>` element updated by a few lines of JS on `change`) so the label + glyph are
  both visible. Applies to both banner pages.

---

## 5. Invites — add multiple emails at once ("+")

### Current state
`FamilyInvitationCreateForm` takes a single `recipient_email`; the POST handler
creates one invite + sends one email.

### Design
- On `family_admin_invites.html`, turn the single Recipient Email input into a
  **repeatable list**: one email input per row plus a **"+ Add another"** button
  that clones a blank row client-side; each row gets a small "remove" control.
  The `role` and `expires_in_days` selects apply to the whole batch (one value).
- Backend: accept multiple `recipient_email` values (`request.POST.getlist`).
  Validate each; for each valid, distinct email create one `FamilyInvitation` and
  send one email, reusing the existing single-invite creation path in a loop
  inside a transaction.
- **Result reporting:** a summary message — e.g. "Sent 3 invites; 1 skipped
  (invalid email), 1 skipped (already a member)." Per-email failures never abort
  the whole batch; valid ones still send.
- The single-email path stays supported (a batch of one). This whole section is
  hidden when entries are locked (see nit 2).
- Keep the existing "invite link shown once" behavior; with a batch, show the
  created links/summary appropriately (list the created invite IDs; links remain
  one-time via email as today — do not persist/redisplay them).

---

## 6. Winners page overhaul — read-only with edit override

### Current state
`family_pool_admin_winners` is a fully manual weekly-winner setter
(`FamilyWeekWinnerForm` → mutates `userSeasonPoints.week_N_winner`). Automation
(`update_weekly_winners`, `update_season_winners` in the scheduler) already
computes winners.

### Design (decision: read-only + owner-only edit override)
- **Default view = read-only.** For the selected week, show the
  automation-computed winner (the current `week_N_winner` row), perfect-week
  members, and the bonus applied — presented as informational, not a form.
- **Override control:** an owner-only (`membership.role == owner`) collapsed
  "Correct this week's winner" section that, when expanded, reveals the existing
  winner-picker form. Submitting it uses the **existing** POST handler and audit
  log (`WEEK_WINNER_UPDATED`) unchanged — we're only relocating it behind a
  disclosure and gating it to owners.
- Copy explains that winners are set automatically and this override is only for
  correcting grading mistakes.
- Admins (non-owner) see the read-only view without the override affordance.
- No change to the scoring/automation backend; no change to `set_week_winner`.

---

## 7. Create-family page visual polish

### Current state
`create_family.html` is functional and "looks nice" per the user but can be
improved.

### Design
- Pure presentation pass, **no functional/field changes**. Load the
  `frontend-design` skill for aesthetic direction during implementation.
- Improve visual hierarchy: stronger hero/intro, clearer sectioning of the
  rules/settings, better spacing and grouping, consistent input styling, and
  polished light/dark treatment. Keep all existing form fields, names, and
  validation intact so the create flow and its tests still pass.

---

## 8. Superadmin email page — column alignment (desktop)

### Current state
`superadmin/email.html` uses
`grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]`. Left column is a
`space-y-4` stack of cards (one is conditionally `hidden`); right column is the
"Current status" card. The two columns don't line up on desktop.

### Design
- Reproduce on localhost in the browser, confirm the exact misalignment, then
  fix the layout so the left and right columns share a consistent top alignment
  (e.g. ensure grid items align to `start`, and the columns' first cards begin at
  the same Y regardless of the conditionally-hidden provider-settings card).
- Purely a CSS/markup fix in the template; no view changes. Verify visually in
  both light and dark and at the `lg` breakpoint boundary.

---

## 9. Superadmin — force-delete a family (cleanup test data)

### Current state
`pickem_superadmin/views/families.py` supports editing families and (in the
homepage app) deactivating them, but there is no hard delete. Family/Pool FKs are
mostly `on_delete=PROTECT`, so `family.delete()` would fail.

### Design (decision: type-the-slug confirm; never deletes Users)
- New service `force_delete_family(family)` in `pickem_superadmin/services.py`
  that, inside a single `transaction.atomic()`, deletes related rows in
  dependency order, then the family. **Order (children → parent):**
  1. `GamePicks` (by pool)
  2. `userPoints`, `userSeasonPoints`, `userStats` (by pool)
  3. `MessageBoardVote` → `MessageBoardComment` → `MessageBoardPost` (by family)
  4. `FamilyAuditLog` (by family)
  5. `FamilyInvitation` (by family)
  6. `PoolSettings` (by pool)
  7. `FamilyMembership` (by family)
  8. `SiteBanner` (family-scoped rows, by family)
  9. `Pool` (by family)
  10. `Family`
- **Never deletes `User` rows** (or `UserProfile`). Memberships/picks/points are
  removed, but the underlying accounts remain.
- **Audit:** capture a before-snapshot (family slug/name, pool count, member
  count, counts of each deleted model) into the audit `changes`, then log via
  `log_action()` with a new `SuperAdminAuditLog.Action.FAMILY_FORCE_DELETED`
  before/after the mutation, per the repo rule (never call
  `SuperAdminAuditLog.objects.create()` directly). The audit row survives the
  deletion (it stores `target_id` as a string, no FK to the deleted family).
- **View + URL:** `superadmin:family_force_delete` (`@superadmin_required`,
  `@require_POST`). Confirmation guard: operator must type the family's exact
  `slug`; mismatch → error message, no deletion (mirrors `pick_delete`).
- **UI (`superadmin/families.html`):** a per-row danger control (e.g. a "Delete"
  button that reveals a small confirm form with the slug input), clearly styled
  as destructive. Include the affected counts so the operator sees the blast
  radius before confirming.
- Add to `tests/test_auth.py` URL coverage (the new URL needs a gate test) and
  test the cascade + user-preservation.

---

## 10. Superadmin nav order — audit last, jobs & logs adjacent

### Current state
`superadmin/base.html` nav order: overview, users, email, pools, families, teams,
**jobs, audit, logs**.

### Design
- Reorder to: overview, users, email, pools, families, teams, **jobs, logs,
  audit** — i.e. swap `audit` and `logs` so jobs+logs are adjacent and audit is
  last. Single template edit; no logic change.

---

## Testing strategy

Each nit gets focused coverage; run `python manage.py test`
(`--settings=pickem.test_settings` to match CI):

- **1:** migration backfills mode correctly; `is_pick_locked_for_pool` honors both
  modes; submit rejects a late pick under each mode; template renders the dropdown.
- **2:** invite-create rejected when pool locked; redemption of a prior link
  rejected for a new user; form hidden in template when locked.
- **3:** payout hidden markup grouped in entry-fee card (server renders it there);
  JS toggle covered by an inline behavior check (best-effort — Django tests can't
  execute JS, so keep the server contract correct and verify JS manually).
- **4:** both banner forms use the Select choices; unknown existing value stays
  selectable.
- **5:** batch create makes N invites and sends N emails; partial failures
  reported; single email still works.
- **6:** read-only render for admins; override present only for owners; POST
  handler + audit unchanged and still works.
- **7:** create-family flow still submits and validates (no field regressions).
- **8:** manual visual verification in browser (layout-only).
- **9:** cascade deletes all listed models for a family; Users/UserProfiles
  preserved; slug-mismatch aborts; audit row written; URL gate test added.
- **10:** nav renders in the new order.

## Out of scope / non-goals
- No changes to the scoring/automation engines (nits 1, 6 reuse them as-is).
- No new against-the-spread or playoff functionality (still locked elsewhere).
- Nit 7 is visual only — no new create-family capabilities.
- Force-delete never removes user accounts.
