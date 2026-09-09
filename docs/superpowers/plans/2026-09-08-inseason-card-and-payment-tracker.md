# In-season Card + Payment Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A second commissioner lobby card for during the season, and an opt-in per-pool payment tracker with a commissioner page and a quiet lobby notice for unpaid players.

**Architecture:** The lobby view swaps its `show_commissioner_setup` boolean for a `commissioner_card` phase string so exactly one card can render. Payment state is a new `PoolMemberPayment` row per (pool, user, season), where absence means unpaid; a `PoolSettings.payment_tracking_enabled` flag (default False) gates the admin page and the lobby notice.

**Tech Stack:** Django 5.2, Tailwind (compiled `tailwind.css`), `django.test.TestCase`, Python 3.12, uv.

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-09-08-inseason-card-and-payment-tracker-design.md`.
- Branch `feat/commissioner-inseason-card-and-payments`, already checked out.
- Tests: `uv run python manage.py test <label> --settings=pickem.test_settings` from `pickem/`.
- **Never** add a `?v=` cache-buster to a `{% static %}` URL.
- Any new Tailwind utility requires `npm run build:prod` and committing `tailwind.css`.
- Every required form field MUST be rendered in the form that posts it (the PR #175 bug class).
- Commissioner test is `role_allows(membership.role, FamilyMembership.Role.ADMIN)`.
- Commit trailer:
  ```text
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EKQvoUBZ6qDWj5YsRS8nY7
  ```

## File Structure

- **Modify** `pickem/pickem_api/models.py` — `PoolSettings.payment_tracking_enabled`, new `PoolMemberPayment`, new `FamilyAuditLog.Action.PAYMENT_UPDATED`.
- **Create** `pickem/pickem_api/migrations/00XX_payment_tracker.py` — generated.
- **Modify** `pickem/pickem_homepage/forms.py` — `payment_tracking_enabled` on `PoolRulesForm`.
- **Modify** `pickem/pickem_homepage/views.py` — `commissioner_card` phase, lobby unpaid notice, `family_pool_admin_payments` view.
- **Modify** `pickem/pickem_homepage/urls.py` — payments route.
- **Create** `pickem/pickem_homepage/templates/pickem/family_admin_payments.html`.
- **Modify** `family_pool_home.html` (both cards + notice), `family_admin.html` (nav link), `family_admin_settings.html` (render the toggle).
- **Modify** `pickem/pickem_homepage/tests.py` — extend `CommissionerSetupCardTests`, add payment tests.

---

### Task 1: Model, settings flag, audit action

**Files:** `pickem_api/models.py`, new migration, `pickem_homepage/forms.py`, `family_admin_settings.html`

- [ ] Add to `PoolSettings`:
  ```python
  payment_tracking_enabled = models.BooleanField(
      default=False,
      help_text="Track which members have paid the entry fee (opt-in).",
  )
  ```
- [ ] Add `PAYMENT_UPDATED = 'payment_updated', 'Payment status updated'` to `FamilyAuditLog.Action`.
- [ ] Add `PoolMemberPayment` with fields per the design doc, `unique_together = (('pool', 'user', 'gameseason'),)`, `pool` on `PROTECT`, `marked_by` on `SET_NULL`.
- [ ] `payment_tracking_enabled = forms.BooleanField(required=False, ...)` on `PoolRulesForm`, mirroring `entry_fee_enabled`'s widget.
- [ ] Render it in `family_admin_settings.html` beside the entry-fee fields. **Required-field parity:** it is `required=False`, but render it anyway so it can be turned off again.
- [ ] `makemigrations` then `migrate`; run the suite.
- [ ] Commit.

### Task 2: Payments admin page

**Files:** `views.py`, `urls.py`, `family_admin_payments.html`, `family_admin.html`

- [ ] Route `families/<slug:family_slug>/pools/<slug:pool_slug>/admin/payments/` → `family_pool_admin_payments`, name `family_pool_admin_payments`.
- [ ] View gated `@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)`.
  - GET: active memberships joined to their `PoolMemberPayment` row for `(pool, gameseason)`; summary of paid count, member count, and `paid_count * entry_fee_amount` when the fee is set.
  - POST: `user_id` + `paid` (+ optional `note`) → `update_or_create`, setting `marked_by=request.user`, `marked_at=now()`; write `FamilyAuditLog` with `PAYMENT_UPDATED`; redirect back.
  - When `payment_tracking_enabled` is False, render the same template in an "off" state linking to Pool Settings. Do **not** 404.
- [ ] Template lists members with a paid toggle and note field; shows `marked_by`/`marked_at`.
- [ ] Add a Payments link to the family admin nav, shown only when the toggle is on.
- [ ] Tests: gate (member 404, admin 200, owner 200), mark paid writes row + audit, unmark clears, off-state renders without member rows.
- [ ] Commit.

### Task 3: Lobby unpaid notice

**Files:** `views.py`, `family_pool_home.html`, `tests.py`

- [ ] In `family_pool_home`, compute `show_unpaid_notice` = toggle on **and** viewer has no `PoolMemberPayment(paid=True)` for this pool+season. Expose `entry_fee_amount` for the copy.
- [ ] Quiet inline notice near the top of the lobby, `data-testid="unpaid-notice"`. Informational only.
- [ ] Tests: hidden when toggle off; shown when on and unpaid; hidden once paid; scoped to pool and season (a paid row in another pool/season does not suppress it).
- [ ] Commit.

### Task 4: In-season commissioner card

**Files:** `views.py`, `family_pool_home.html`, `tests.py`

- [ ] Replace `show_commissioner_setup` with `commissioner_card`:
  ```python
  commissioner_card = ''
  if role_allows(tenant_context.membership.role, FamilyMembership.Role.ADMIN):
      season_kickoff = (...)  # unchanged query
      commissioner_card = (
          'preseason'
          if season_kickoff is None or timezone.now() < season_kickoff
          else 'inseason'
      )
  ```
- [ ] Template: `{% if commissioner_card == 'preseason' %}` (existing card) `{% elif commissioner_card == 'inseason' %}` (new card, `data-testid="commissioner-inseason"`, heading "Running your pool", links to lobby notes / settings / members).
- [ ] Update the existing `CommissionerSetupCardTests` to the new context key; add in-season tests, including that the in-season card does **not** contain the invite URL.
- [ ] Commit.

### Task 5: Verify

- [ ] `uv run python manage.py check` and `makemigrations --check --dry-run`.
- [ ] Full suite.
- [ ] `npm run build:prod`; commit `tailwind.css` only if it actually changed.
- [ ] Commit.
