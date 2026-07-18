# Commissioner & Superadmin Nits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 10 independent commissioner/superadmin fixes: a configurable picks-lock mode, late-join invite lockout, payout/entry-fee grouping, a banner icon dropdown, batch invite emails, a read-only winners page with override, create-family polish, a superadmin email alignment fix, family force-delete, and a superadmin nav reorder.

**Architecture:** Django 4.0 app. Changes touch models + a data migration (`pickem_api`), template views/forms (`pickem_homepage`), the superadmin console (`pickem_superadmin`), the shared lock util (`pickem/utils.py`), and templates. Each nit is self-contained; tasks are ordered so shared plumbing (the picks-lock field rename) lands first.

**Tech Stack:** Django 4.0.2, Django templates + Tailwind CSS, vanilla JS, `pytz`, Django `TestCase`.

## Global Constraints

- Run tests with `python manage.py test --settings=pickem.test_settings` from the `pickem/` directory (matches CI; see memory `local-test-run-recipe`).
- Never call `SuperAdminAuditLog.objects.create()` directly — always go through `log_action()` (`pickem_superadmin/audit.py`).
- Superadmin views must carry `@superadmin_required`; any new superadmin URL needs a gate test in `pickem_superadmin/tests/test_auth.py::test_all_urls_are_covered`.
- Force-delete must NEVER delete `User` or `UserProfile` rows.
- `pick_type=against_spread` and `include_playoffs` remain locked/disabled — do not touch.
- All new user-facing copy uses they/them and plain language.
- Commit after each task with the trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Working directory for all shell commands: `/Users/jim/git/family-pickem/.worktrees/feature-varous-nits/pickem` unless noted.

---

### Task 1: Picks-lock mode — model field + data migration

**Files:**
- Modify: `pickem/pickem_api/models.py:200-223` (add `PicksLockMode`, replace `picks_lock_at_kickoff`)
- Create: `pickem/pickem_api/migrations/00NN_picks_lock_mode.py` (schema + data)
- Test: `pickem/pickem_api/tests.py` (append)

**Interfaces:**
- Produces: `PoolSettings.PicksLockMode` (`.KICKOFF = 'kickoff'`, `.SUNDAY_1PM = 'sunday_1pm'`); `PoolSettings.picks_lock_mode` CharField (default `KICKOFF`). Removes `PoolSettings.picks_lock_at_kickoff`.

- [ ] **Step 1: Write the failing test**

Append to `pickem/pickem_api/tests.py`:
```python
class PicksLockModeTests(TestCase):
    def test_default_mode_is_kickoff(self):
        from pickem_api.models import Family, Pool, PoolSettings
        fam = Family.objects.create(name="LockFam", slug="lockfam")
        pool = Pool.objects.create(family=fam, name="P", slug="p", season=2425)
        settings = PoolSettings.objects.create(pool=pool)
        self.assertEqual(settings.picks_lock_mode, PoolSettings.PicksLockMode.KICKOFF)

    def test_mode_choices(self):
        from pickem_api.models import PoolSettings
        values = {c[0] for c in PoolSettings.PicksLockMode.choices}
        self.assertEqual(values, {"kickoff", "sunday_1pm"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test pickem_api.tests.PicksLockModeTests --settings=pickem.test_settings`
Expected: FAIL — `PoolSettings` has no attribute `PicksLockMode`.

- [ ] **Step 3: Edit the model**

In `pickem/pickem_api/models.py`, add the enum near the other choice classes (after `PickType`, ~line 202):
```python
    class PicksLockMode(models.TextChoices):
        KICKOFF = 'kickoff', 'Lock each game at kickoff'
        SUNDAY_1PM = 'sunday_1pm', 'Weekly cutoff — Sunday 1PM ET'
```
Replace the `picks_lock_at_kickoff` field (lines 220-223) with:
```python
    picks_lock_mode = models.CharField(
        max_length=16,
        choices=PicksLockMode.choices,
        default=PicksLockMode.KICKOFF,
        help_text="When picks lock: each game at kickoff, or a weekly Sunday 1PM ET cutoff",
    )
```

- [ ] **Step 4: Create the migration**

Run: `python manage.py makemigrations pickem_api --name picks_lock_mode`
Then edit the generated migration to add a data-migration step BEFORE the `RemoveField`. The operations list must be: `AddField(picks_lock_mode)`, then `RunPython(backfill, reverse)`, then `RemoveField(picks_lock_at_kickoff)`. Insert:
```python
def backfill_lock_mode(apps, schema_editor):
    PoolSettings = apps.get_model('pickem_api', 'PoolSettings')
    PoolSettings.objects.filter(picks_lock_at_kickoff=False).update(picks_lock_mode='sunday_1pm')
    PoolSettings.objects.filter(picks_lock_at_kickoff=True).update(picks_lock_mode='kickoff')

def reverse_lock_mode(apps, schema_editor):
    PoolSettings = apps.get_model('pickem_api', 'PoolSettings')
    PoolSettings.objects.filter(picks_lock_mode='sunday_1pm').update(picks_lock_at_kickoff=False)
    PoolSettings.objects.filter(picks_lock_mode='kickoff').update(picks_lock_at_kickoff=True)
```
Wire it as `migrations.RunPython(backfill_lock_mode, reverse_lock_mode)` positioned between the add and remove operations. (If `makemigrations` splits add/remove, keep them in one file in that order.)

- [ ] **Step 5: Run migrations + test to verify pass**

Run: `python manage.py migrate --settings=pickem.test_settings && python manage.py test pickem_api.tests.PicksLockModeTests --settings=pickem.test_settings`
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add pickem/pickem_api/models.py pickem/pickem_api/migrations/ pickem/pickem_api/tests.py
git commit -m "feat(picks): add PoolSettings.picks_lock_mode field + backfill migration

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Picks-lock — util honors mode

**Files:**
- Modify: `pickem/pickem/utils.py:110-131` (`is_pick_locked_for_pool`)
- Test: `pickem/pickem_homepage/tests.py` (append; has model factories/imports already)

**Interfaces:**
- Consumes: `PoolSettings.PicksLockMode` from Task 1.
- Produces: `is_pick_locked_for_pool(game, pool=None, week_games=None) -> (bool, str)` unchanged signature; now reads `picks_lock_mode`.

- [ ] **Step 1: Write the failing test**

Append to `pickem/pickem_homepage/tests.py` (adjust game/pool factory helpers to match existing patterns in that file — search for existing `GamesAndScores.objects.create` usage and reuse the same required fields):
```python
class PicksLockForPoolModeTests(TestCase):
    def _future_game(self):
        from django.utils import timezone
        from datetime import timedelta
        from pickem_api.models import GamesAndScores
        return GamesAndScores.objects.create(
            id=990001, gameseason=2425, gameWeek='1', competition='nfl',
            statusType='notstarted',
            startTimestamp=timezone.now() + timedelta(days=2),
            awayTeamSlug='aaa', homeTeamSlug='bbb',
        )

    def test_sunday_1pm_mode_uses_week_rule(self):
        from pickem_api.models import Family, Pool, PoolSettings
        from pickem.utils import is_pick_locked_for_pool
        fam = Family.objects.create(name="M", slug="m")
        pool = Pool.objects.create(family=fam, name="p", slug="p", season=2425)
        PoolSettings.objects.create(pool=pool, picks_lock_mode=PoolSettings.PicksLockMode.SUNDAY_1PM)
        game = self._future_game()
        locked, _reason = is_pick_locked_for_pool(game, pool)
        self.assertFalse(locked)  # future game, before any cutoff

    def test_kickoff_mode_future_game_unlocked(self):
        from pickem_api.models import Family, Pool, PoolSettings
        from pickem.utils import is_pick_locked_for_pool
        fam = Family.objects.create(name="K", slug="k")
        pool = Pool.objects.create(family=fam, name="p", slug="p", season=2425)
        PoolSettings.objects.create(pool=pool, picks_lock_mode=PoolSettings.PicksLockMode.KICKOFF)
        game = self._future_game()
        locked, _reason = is_pick_locked_for_pool(game, pool)
        self.assertFalse(locked)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test pickem_homepage.tests.PicksLockForPoolModeTests --settings=pickem.test_settings`
Expected: FAIL — reads removed `picks_lock_at_kickoff`.

- [ ] **Step 3: Rewrite `is_pick_locked_for_pool`**

Replace the body (`pickem/pickem/utils.py:110-131`) with:
```python
def is_pick_locked_for_pool(game, pool=None, week_games=None):
    """Determine pick lock status using pool-specific locking settings."""
    if pool is None:
        return is_pick_locked(game, week_games)

    from pickem_api.models import PoolSettings

    settings = getattr(pool, "settings", None)
    if settings is None:
        settings = PoolSettings.objects.filter(pool=pool).first()

    lock_mode = getattr(settings, "picks_lock_mode", None) if settings else None
    if lock_mode is None:
        lock_mode = PoolSettings.PicksLockMode.KICKOFF

    if lock_mode == PoolSettings.PicksLockMode.KICKOFF:
        est = pytz.timezone('US/Eastern')
        now_est = datetime.now(est)
        if game.statusType != 'notstarted':
            return True, "Game has already started"
        game_start_est = game.startTimestamp.astimezone(est)
        if now_est >= game_start_est:
            return True, "Game has started"
        return False, "Game not started yet"

    return is_pick_locked(game, week_games)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test pickem_homepage.tests.PicksLockForPoolModeTests --settings=pickem.test_settings`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add pickem/pickem/utils.py pickem/pickem_homepage/tests.py
git commit -m "feat(picks): is_pick_locked_for_pool honors picks_lock_mode

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Picks-lock — commissioner form + settings template dropdown

**Files:**
- Modify: `pickem/pickem_homepage/forms.py:72-78` (`PoolRulesForm`)
- Modify: `pickem/pickem_homepage/views.py:1254-1256` (`ADMIN_POOL_SETTINGS_FIELDS`)
- Modify: `pickem/pickem_homepage/templates/pickem/family_admin_settings.html:74-78` (render dropdown)
- Test: `pickem/pickem_homepage/tests.py` (append)

**Interfaces:**
- Consumes: `PoolSettings.PicksLockMode`.
- Produces: `PoolRulesForm.picks_lock_mode` ChoiceField (inherited by `FamilyAdminSettingsForm` and `CreateFamilyForm`).

- [ ] **Step 1: Write the failing test**
```python
class PicksLockFormFieldTests(TestCase):
    def test_form_has_lock_mode_choice(self):
        from pickem_homepage.forms import PoolRulesForm
        form = PoolRulesForm()
        self.assertIn('picks_lock_mode', form.fields)
        self.assertNotIn('picks_lock_at_kickoff', form.fields)

    def test_admin_settings_fields_list_updated(self):
        from pickem_homepage.views import ADMIN_POOL_SETTINGS_FIELDS
        self.assertIn('picks_lock_mode', ADMIN_POOL_SETTINGS_FIELDS)
        self.assertNotIn('picks_lock_at_kickoff', ADMIN_POOL_SETTINGS_FIELDS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test pickem_homepage.tests.PicksLockFormFieldTests --settings=pickem.test_settings`
Expected: FAIL.

- [ ] **Step 3: Edit the form**

In `pickem/pickem_homepage/forms.py`, replace the `picks_lock_at_kickoff` BooleanField (lines 72-78) with:
```python
    picks_lock_mode = forms.ChoiceField(
        label="Pick locking",
        choices=PoolSettings.PicksLockMode.choices,
        help_text="Choose when picks lock each week.",
        widget=forms.Select(attrs={'class': ADMIN_TEXT_INPUT_CLASSES}),
    )
```

- [ ] **Step 4: Edit the fields list**

In `pickem/pickem_homepage/views.py`, change the first entry of `ADMIN_POOL_SETTINGS_FIELDS` from `'picks_lock_at_kickoff',` to `'picks_lock_mode',`.

- [ ] **Step 5: Edit the settings template**

In `family_admin_settings.html`, replace the block that renders `{{ form.picks_lock_at_kickoff }}` (around line 74-84) with a labeled select. Replace the checkbox `<label>` wrapper for pick locking with:
```html
                <div>
                    <label class="block text-sm font-semibold text-text-dark dark:text-white" for="{{ form.picks_lock_mode.id_for_label }}">
                        {{ form.picks_lock_mode.label }}
                    </label>
                    <div class="mt-2">{{ form.picks_lock_mode }}</div>
                    <p class="mt-2 text-xs text-text-secondary-light dark:text-text-secondary">{{ form.picks_lock_mode.help_text }}</p>
                    {% for error in form.picks_lock_mode.errors %}
                    <p class="mt-2 text-sm font-semibold text-red-600 dark:text-red-400">{{ error }}</p>
                    {% endfor %}
                </div>
```
(Keep the surrounding `allow_tiebreaker` / `include_playoffs` checkboxes as-is.)

- [ ] **Step 6: Run tests + smoke the settings page**

Run: `python manage.py test pickem_homepage.tests.PicksLockFormFieldTests --settings=pickem.test_settings`
Expected: PASS.
Then load `http://localhost:8000/families/legacy-family-league/pools/pickem-pool/admin/settings/` and confirm the "Pick locking" dropdown renders with both options.

- [ ] **Step 7: Commit**
```bash
git add pickem/pickem_homepage/forms.py pickem/pickem_homepage/views.py pickem/pickem_homepage/templates/pickem/family_admin_settings.html pickem/pickem_homepage/tests.py
git commit -m "feat(picks): commissioner pick-locking dropdown

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Picks-lock — frontend picks.html honors pool setting (the bug)

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/picks.html` (lines ~209, 250, 307, 320, 327, 134-135)
- Test: `pickem/pickem_homepage/tests.py` (append — assert rendered markup)

**Interfaces:**
- Consumes: `is_game_locked_for_pool` filter (already registered in `pickem_homepage_extras.py`), `pool` in context.

- [ ] **Step 1: Write the failing test**

This test renders the picks page for a Sunday-1PM pool with a future game and asserts the pick cards are NOT force-locked by `statusType`. Model the setup on the existing tenant-pick tests in `tests.py` (search `render_pick_page` / `family_pool_game_picks`). Minimal assertion:
```python
class PicksPageLockFilterTests(TestCase):
    def test_template_uses_pool_aware_filter(self):
        # Guard against regressing to statusType-only gating.
        import pathlib
        tpl = pathlib.Path('pickem_homepage/templates/pickem/picks.html').read_text()
        # The interactive pick options must gate on the pool-aware filter.
        self.assertIn('is_game_locked_for_pool:pool', tpl)
        # The old kickoff-only gate must be gone from the team-option cards.
        self.assertNotIn("game.statusType != 'notstarted' or auth_required", tpl)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test pickem_homepage.tests.PicksPageLockFilterTests --settings=pickem.test_settings`
Expected: FAIL — old gate string still present.

- [ ] **Step 3: Edit picks.html**

Replace each pick-selection gate that reads `{% if game.statusType != 'notstarted' or auth_required %}` (the two team-option `<div>`s at ~209 and ~250) with:
```django
{% if game|is_game_locked_for_pool:pool or auth_required %}
```
Replace the tiebreaker input gates `{% if game.statusType != 'notstarted' %}` (~307, ~320) and the "Locked Game Message" gate (~327) and the LOCKED badge gate (~134) with:
```django
{% if game|is_game_locked_for_pool:pool %}
```
At the top of the template (after `{% block content %}`), ensure the filter library is loaded — confirm `{% load pickem_homepage_extras %}` is present near the top; add it if missing.
Note: `pool` is `None` for the logged-out `/picks/` route; the filter falls back to `is_game_locked` (kickoff/Sunday rule) via its `except`, which is acceptable for the anonymous preview.

- [ ] **Step 4: Run test + manual smoke**

Run: `python manage.py test pickem_homepage.tests.PicksPageLockFilterTests --settings=pickem.test_settings`
Expected: PASS.
Manual: load the picks page for the pool; confirm future games are pickable and started games show LOCKED.

- [ ] **Step 5: Commit**
```bash
git add pickem/pickem_homepage/templates/pickem/picks.html pickem/pickem_homepage/tests.py
git commit -m "fix(picks): pick UI locks per pool setting, not just kickoff

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Picks-lock — superadmin pools matrix field

**Files:**
- Modify: `pickem/pickem_superadmin/forms.py:21-41` (`PoolSettingsRowForm`)
- Modify: `pickem/pickem_superadmin/templates/superadmin/pools.html` (column header + cell)
- Test: `pickem/pickem_superadmin/tests/` (append to the pools test module)

**Interfaces:**
- Consumes: `PoolSettings.picks_lock_mode`.

- [ ] **Step 1: Write the failing test**

Find the existing pools test file (`ls pickem_superadmin/tests/`), then append:
```python
def test_pools_row_form_has_lock_mode(self):
    from pickem_superadmin.forms import PoolSettingsRowForm
    form = PoolSettingsRowForm()
    self.assertIn('picks_lock_mode', form.fields)
    self.assertNotIn('picks_lock_at_kickoff', form.fields)
```
(Place it in the pools-matrix test class; if none exists, add a `SimpleTestCase`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test pickem_superadmin --settings=pickem.test_settings`
Expected: FAIL on the new assertion.

- [ ] **Step 3: Edit the row form**

In `pickem/pickem_superadmin/forms.py`, in `PoolSettingsRowForm.Meta.fields`, replace `'picks_lock_at_kickoff'` with `'picks_lock_mode'`, and add a widget entry:
```python
            'picks_lock_mode': forms.Select(attrs={'class': CELL}),
```

- [ ] **Step 4: Edit pools.html**

In `superadmin/pools.html`, find the `picks_lock_at_kickoff` header/cell (search the file) and replace the field reference with `picks_lock_mode` (header label "Lock", cell renders `{{ form.picks_lock_mode }}`). If it was rendered as a checkbox, render the select instead.

- [ ] **Step 5: Run tests + manual smoke**

Run: `python manage.py test pickem_superadmin --settings=pickem.test_settings`
Expected: PASS.
Manual: load `/superadmin/pools/`, confirm the Lock column shows a dropdown and saving persists.

- [ ] **Step 6: Commit**
```bash
git add pickem/pickem_superadmin/forms.py pickem/pickem_superadmin/templates/superadmin/pools.html pickem/pickem_superadmin/tests/
git commit -m "feat(superadmin): show picks_lock_mode in pools matrix

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Late-join — hide invite form + reject creation when locked

**Files:**
- Modify: `pickem/pickem_homepage/views.py:2206-2253` (`family_pool_admin_invites`)
- Modify: `pickem/pickem_homepage/templates/pickem/family_admin_invites.html:55-93` (wrap Create Invite section)
- Test: `pickem/pickem_homepage/tests.py` (append)

**Interfaces:**
- Consumes: `pool_entries_locked(pool)` (`views.py:630`), `entries_locked` context flag (already passed by `render_family_admin_invites` — verify; add if missing).

- [ ] **Step 1: Verify the context flag**

Run: `grep -n "entries_locked" pickem_homepage/views.py`
If `render_family_admin_invites` does not already pass `entries_locked`, add `'entries_locked': pool_entries_locked(pool)` to its context dict. (The template already references `entries_locked`.)

- [ ] **Step 2: Write the failing test**
```python
class InviteLockedFormTests(TestCase):
    def test_create_invite_rejected_when_locked(self):
        # Build a family+pool with late_join_policy=lock_after_week_1 and week 1 complete,
        # an owner user, then POST to the invites endpoint. Reuse existing invite-test
        # helpers in this file for auth/tenant setup.
        # Assert: no FamilyInvitation created and a redirect/400 back to the page.
        ...
```
Model the setup on the nearest existing invite test (search `family_pool_admin_invites` in `tests.py`). Assert `FamilyInvitation.objects.count()` is unchanged after the POST and that a warning message is present.

- [ ] **Step 3: Run test to verify it fails**

Run: `python manage.py test pickem_homepage.tests.InviteLockedFormTests --settings=pickem.test_settings`
Expected: FAIL (invite gets created today).

- [ ] **Step 4: Guard the POST handler**

In `family_pool_admin_invites`, immediately inside `if request.method == 'POST':` (before `form.is_valid()`), add:
```python
        if pool_entries_locked(tenant_context.pool):
            messages.error(
                request,
                "Entries are locked for this pool, so new invites can't be created.",
            )
            return render_family_admin_invites(request, tenant_context, form, status=400)
```

- [ ] **Step 5: Hide the form in the template**

In `family_admin_invites.html`, wrap the entire "Create Invite" `<section>` (lines ~55-93) in `{% if not entries_locked %} ... {% endif %}`. The amber locked notice (lines 28-37) already renders separately and stays.

- [ ] **Step 6: Run test to verify it passes**

Run: `python manage.py test pickem_homepage.tests.InviteLockedFormTests --settings=pickem.test_settings`
Expected: PASS.

- [ ] **Step 7: Commit**
```bash
git add pickem/pickem_homepage/views.py pickem/pickem_homepage/templates/pickem/family_admin_invites.html pickem/pickem_homepage/tests.py
git commit -m "fix(invites): hide + reject invite creation when entries locked

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Late-join — regression test for stale-link redemption

**Files:**
- Test: `pickem/pickem_homepage/tests.py` (append only — backend already blocks at `views.py:671`)

**Interfaces:**
- Consumes: `accept_invitation_for_user`, `ENTRIES_LOCKED_MESSAGE`.

- [ ] **Step 1: Write the test**
```python
class StaleInviteRedemptionTests(TestCase):
    def test_prior_link_rejected_for_new_user_when_locked(self):
        # Create family+pool with lock_after_week_1 and week 1 complete.
        # Create a valid invitation (issued earlier). New user (not a member) redeems.
        # Assert accept_invitation_for_user returns error == ENTRIES_LOCKED_MESSAGE
        # and no FamilyMembership is created for that user.
        ...
```
Reuse invite-creation helpers already in `tests.py`. Assert the returned `error` equals `ENTRIES_LOCKED_MESSAGE` and membership count for the new user is 0.

- [ ] **Step 2: Run test to verify it passes**

Run: `python manage.py test pickem_homepage.tests.StaleInviteRedemptionTests --settings=pickem.test_settings`
Expected: PASS (documents existing correct behavior). If it FAILS, fix `accept_invitation_for_user` to return `ENTRIES_LOCKED_MESSAGE` per the design before continuing.

- [ ] **Step 3: Commit**
```bash
git add pickem/pickem_homepage/tests.py
git commit -m "test(invites): stale link rejected for new user when locked

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Payout structure grouped under Entry Fee (conditional)

**Files:**
- Modify: `pickem/pickem_homepage/views.py` (the `rule_choice_fields` builder — search it)
- Modify: `pickem/pickem_homepage/templates/pickem/family_admin_settings.html:179-199` (Entry Fee card) + add a small `<script>`
- Test: `pickem/pickem_homepage/tests.py` (append — assert render location)

**Interfaces:**
- Consumes: `form.payout_structure`, `form.entry_fee_enabled`, `form.entry_fee_amount`.

- [ ] **Step 1: Locate the field grouping**

Run: `grep -n "rule_choice_fields\|payout_structure" pickem_homepage/views.py`
Identify where `rule_choice_fields` is assembled (the list of fields the template loops at line 140). Remove `payout_structure` from that list so it no longer renders in the generic loop.

- [ ] **Step 2: Write the failing test**
```python
class PayoutGroupingTests(TestCase):
    def test_payout_not_in_generic_choice_loop(self):
        import pathlib
        tpl = pathlib.Path('pickem_homepage/templates/pickem/family_admin_settings.html').read_text()
        # payout_structure must render inside the entry-fee card, keyed by name.
        self.assertIn('form.payout_structure', tpl)
        # And the entry-fee card must contain the payout wrapper marker.
        self.assertIn('data-payout-group', tpl)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python manage.py test pickem_homepage.tests.PayoutGroupingTests --settings=pickem.test_settings`
Expected: FAIL.

- [ ] **Step 4: Render payout inside the Entry Fee card**

In `family_admin_settings.html`, inside the Entry Fee card `<div>` (after the amount input block, before its closing `</div>` at ~198), add:
```html
                    <div class="mt-3" data-payout-group hidden>
                        <label class="block text-xs font-semibold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary" for="{{ form.payout_structure.id_for_label }}">
                            {{ form.payout_structure.label }}
                        </label>
                        <div class="mt-1">{{ form.payout_structure }}</div>
                        {% for error in form.payout_structure.errors %}
                        <p class="mt-2 text-sm font-semibold text-red-600 dark:text-red-400">{{ error }}</p>
                        {% endfor %}
                    </div>
```
Add `data-entry-fee-enabled` to the `{{ form.entry_fee_enabled }}` checkbox wrapper and `data-entry-fee-amount` to the amount input's container so JS can find them. Then add before `{% endblock %}`:
```html
<script>
(function () {
  const group = document.querySelector('[data-payout-group]');
  if (!group) return;
  const enabled = document.querySelector('#{{ form.entry_fee_enabled.id_for_label }}');
  const amount = document.querySelector('#{{ form.entry_fee_amount.id_for_label }}');
  function sync() {
    const on = enabled && enabled.checked && amount && Number(amount.value) > 0;
    group.hidden = !on;
  }
  if (enabled) enabled.addEventListener('change', sync);
  if (amount) amount.addEventListener('input', sync);
  sync();
})();
</script>
```

- [ ] **Step 5: Run test + manual smoke**

Run: `python manage.py test pickem_homepage.tests.PayoutGroupingTests --settings=pickem.test_settings`
Expected: PASS.
Manual: on the settings page, payout hidden until Entry Fee is checked AND amount > 0.

- [ ] **Step 6: Commit**
```bash
git add pickem/pickem_homepage/views.py pickem/pickem_homepage/templates/pickem/family_admin_settings.html pickem/pickem_homepage/tests.py
git commit -m "feat(settings): group payout under entry fee, show only when fee > 0

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Banner icon dropdown (both banner forms)

**Files:**
- Modify: `pickem/pickem_homepage/forms.py:560-680` (`SiteBannerForm`, `FamilyBannerForm`, add shared `BANNER_ICON_CHOICES`)
- Modify: `pickem/pickem_homepage/templates/pickem/family_admin_banners.html` (add preview `<i>` + JS)
- Modify: `pickem/pickem_superadmin/templates/superadmin/overview.html` (site banner form — add preview)
- Test: `pickem/pickem_homepage/tests.py` (append)

**Interfaces:**
- Produces: `pickem_homepage.forms.BANNER_ICON_CHOICES: list[tuple[str, str]]`.

- [ ] **Step 1: Write the failing test**
```python
class BannerIconChoicesTests(TestCase):
    def test_both_forms_use_select(self):
        from django import forms as djf
        from pickem_homepage.forms import SiteBannerForm, FamilyBannerForm, BANNER_ICON_CHOICES
        self.assertTrue(len(BANNER_ICON_CHOICES) >= 10)
        for FormClass in (SiteBannerForm, FamilyBannerForm):
            widget = FormClass().fields['icon'].widget
            self.assertIsInstance(widget, djf.Select)

    def test_unknown_existing_icon_stays_selectable(self):
        from pickem_homepage.forms import FamilyBannerForm
        from pickem_homepage.models import SiteBanner
        b = SiteBanner(icon='fas fa-custom-thing', title='t', description='d')
        form = FamilyBannerForm(instance=b)
        rendered = str(form['icon'])
        self.assertIn('fas fa-custom-thing', rendered)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test pickem_homepage.tests.BannerIconChoicesTests --settings=pickem.test_settings`
Expected: FAIL — no `BANNER_ICON_CHOICES`; icon is a TextInput.

- [ ] **Step 3: Add the shared choices + swap widgets**

In `pickem/pickem_homepage/forms.py`, above `SiteBannerForm` (~line 559), add:
```python
BANNER_ICON_CHOICES = [
    ('fas fa-bullhorn', 'Announcement'),
    ('fas fa-info-circle', 'Info'),
    ('fas fa-exclamation-triangle', 'Warning'),
    ('fas fa-check-circle', 'Success'),
    ('fas fa-trophy', 'Trophy'),
    ('fas fa-football-ball', 'Football'),
    ('fas fa-star', 'Star'),
    ('fas fa-fire', 'Hot'),
    ('fas fa-gift', 'Gift'),
    ('fas fa-bell', 'Bell'),
    ('fas fa-clock', 'Reminder'),
    ('fas fa-calendar', 'Calendar'),
    ('fas fa-users', 'Members'),
    ('fas fa-dollar-sign', 'Money'),
    ('fas fa-wrench', 'Maintenance'),
]
```
For BOTH forms, change the `icon` widget to `forms.Select(...)` (keep existing CSS classes) and, in each form's `__init__`, set choices with a fallback for unknown stored values:
```python
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = list(BANNER_ICON_CHOICES)
        current = (self.instance.icon or '').strip() if self.instance and self.instance.pk else ''
        if current and current not in dict(choices):
            choices = [(current, f'{current} (current)')] + choices
        self.fields['icon'].choices = choices
        self.fields['icon'].widget.choices = choices
```
(Preserve the existing `FamilyBannerForm.__init__` default of `fas fa-bullhorn` for new instances — set `self.fields['icon'].initial = 'fas fa-bullhorn'` when there's no pk.)

- [ ] **Step 4: Add a live preview to both templates**

In `family_admin_banners.html` next to the icon select, add `<i data-icon-preview class="{{ form.icon.value|default:'fas fa-bullhorn' }} text-lg"></i>` and a script that updates its className on select `change`. Do the same in `superadmin/overview.html` for the site banner form's icon field. Example script:
```html
<script>
(function () {
  document.querySelectorAll('select[name="icon"]').forEach(function (sel) {
    const preview = sel.closest('form').querySelector('[data-icon-preview]');
    if (!preview) return;
    sel.addEventListener('change', function () { preview.className = sel.value + ' text-lg'; });
  });
})();
</script>
```

- [ ] **Step 5: Run test + manual smoke**

Run: `python manage.py test pickem_homepage.tests.BannerIconChoicesTests --settings=pickem.test_settings`
Expected: PASS.
Manual: family banners page + superadmin overview banner form show an icon dropdown with a glyph preview.

- [ ] **Step 6: Commit**
```bash
git add pickem/pickem_homepage/forms.py pickem/pickem_homepage/templates/pickem/family_admin_banners.html pickem/pickem_superadmin/templates/superadmin/overview.html pickem/pickem_homepage/tests.py
git commit -m "feat(banners): icon dropdown with live preview

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: Invites — batch multiple emails at once

**Files:**
- Modify: `pickem/pickem_homepage/forms.py:387-433` area (add a batch-email form or accept a list)
- Modify: `pickem/pickem_homepage/views.py:2206-2253` (`family_pool_admin_invites` — loop over emails)
- Modify: `pickem/pickem_homepage/templates/pickem/family_admin_invites.html:62-92` (repeatable rows + "+")
- Test: `pickem/pickem_homepage/tests.py` (append)

**Interfaces:**
- Consumes: `create_admin_invitation(...)` (`views.py:2147`), `handle_targeted_invite_email_feedback`.

- [ ] **Step 1: Write the failing test**
```python
class BatchInviteTests(TestCase):
    def test_multiple_emails_create_multiple_invites(self):
        # Owner posts recipient_email=['a@x.com','b@x.com'] to the invites endpoint.
        # Assert two FamilyInvitation rows created with those recipient_emails.
        ...
    def test_invalid_email_skipped_valid_still_created(self):
        # POST ['good@x.com','not-an-email']; assert one invite created and a
        # message noting one skipped.
        ...
```
Reuse the tenant/owner setup helpers from existing invite tests.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test pickem_homepage.tests.BatchInviteTests --settings=pickem.test_settings`
Expected: FAIL.

- [ ] **Step 3: Accept a list in the view**

Rewrite the POST branch of `family_pool_admin_invites` to read `emails = request.POST.getlist('recipient_email')`, normalize/dedupe (lowercase, strip, drop blanks), validate each with `django.core.validators.validate_email`, and loop:
```python
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError

        raw_emails = [e.strip().lower() for e in request.POST.getlist('recipient_email')]
        emails, seen = [], set()
        for e in raw_emails:
            if e and e not in seen:
                seen.add(e)
                emails.append(e)

        role = request.POST.get('role', FamilyMembership.Role.MEMBER)
        # Validate role against allowed_roles as the single-form did (reuse the form for role/expiry).
        created, skipped_invalid, skipped_member = [], [], []
        with transaction.atomic():
            for email in emails or ['']:  # '' preserves the "no recipient" single-invite path
                if email:
                    try:
                        validate_email(email)
                    except DjangoValidationError:
                        skipped_invalid.append(email)
                        continue
                invitation, raw_code = create_admin_invitation(
                    family=tenant_context.family, pool=tenant_context.pool,
                    actor=request.user, role=role, recipient_email=email or '',
                    expires_in_days=int(request.POST.get('expires_in_days') or 14),
                    request=request,
                )
                created.append((invitation, raw_code))
                handle_targeted_invite_email_feedback(request, invitation=invitation, raw_code=raw_code)
```
Keep role/expiry validation: bind `FamilyInviteCreateForm` once (without `recipient_email`) or validate `role`/`expires_in_days` inline against `allowed_roles`. Build a summary message: `f"Sent {len(created)} invite(s)."` plus skip notes. Do not display invite links for a batch (email delivery only); for a single created invite keep the existing one-time link display.

- [ ] **Step 4: Repeatable email rows in the template**

In `family_admin_invites.html` Create-Invite form, replace the single email input with a container of rows, each `<input name="recipient_email">`, plus a "+ Add another" button and per-row remove. Add JS to clone/remove rows:
```html
<div data-email-rows>
  <div class="flex gap-2" data-email-row>
    <input type="email" name="recipient_email" class="{{ ... same classes ... }}" placeholder="name@example.com">
    <button type="button" class="px-3 text-sm text-red-600" data-remove-row>&times;</button>
  </div>
</div>
<button type="button" class="mt-2 text-sm font-semibold text-primary" data-add-row>+ Add another</button>
<script>
(function () {
  const box = document.querySelector('[data-email-rows]');
  const add = document.querySelector('[data-add-row]');
  if (!box || !add) return;
  add.addEventListener('click', function () {
    const row = box.querySelector('[data-email-row]').cloneNode(true);
    row.querySelector('input').value = '';
    box.appendChild(row);
  });
  box.addEventListener('click', function (e) {
    if (e.target.matches('[data-remove-row]') && box.querySelectorAll('[data-email-row]').length > 1) {
      e.target.closest('[data-email-row]').remove();
    }
  });
})();
</script>
```
This whole section is already wrapped in `{% if not entries_locked %}` from Task 6.

- [ ] **Step 5: Run test + manual smoke**

Run: `python manage.py test pickem_homepage.tests.BatchInviteTests --settings=pickem.test_settings`
Expected: PASS.
Manual: add 3 email rows, submit, confirm 3 invites + a summary message.

- [ ] **Step 6: Commit**
```bash
git add pickem/pickem_homepage/forms.py pickem/pickem_homepage/views.py pickem/pickem_homepage/templates/pickem/family_admin_invites.html pickem/pickem_homepage/tests.py
git commit -m "feat(invites): send multiple invite emails at once

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: Winners page — read-only with owner-only override

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/family_admin_winners.html` (restructure)
- Modify: `pickem/pickem_homepage/views.py:1868-1899` (`render_family_admin_winners` — pass `can_override`)
- Test: `pickem/pickem_homepage/tests.py` (append)

**Interfaces:**
- Consumes: `tenant_context.membership.role`, `FamilyMembership.Role.OWNER`, existing `current_winner`, `candidates`, `FamilyWeekWinnerForm`.
- Produces: context key `can_override` (bool).

- [ ] **Step 1: Write the failing test**
```python
class WinnersOverrideVisibilityTests(TestCase):
    def test_owner_sees_override_admin_does_not(self):
        # Render winners page as owner -> response contains 'Correct this week'
        # Render as admin (non-owner) -> does NOT contain the override form/button.
        ...
```
Reuse tenant/role setup helpers. Assert on `b'Correct this' in response.content` for owner and absence for admin.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test pickem_homepage.tests.WinnersOverrideVisibilityTests --settings=pickem.test_settings`
Expected: FAIL.

- [ ] **Step 3: Pass `can_override` from the view**

In `render_family_admin_winners`, add to context:
```python
        'can_override': tenant_context.membership.role == FamilyMembership.Role.OWNER,
```

- [ ] **Step 4: Restructure the template**

Rework `family_admin_winners.html` so the default is a read-only summary: show `current_winner` (auto-computed), the bonus applied, and perfect-week members as static text ("Winners are set automatically."). Wrap the existing manual `FamilyWeekWinnerForm` UI in:
```django
{% if can_override %}
<details class="mt-6 rounded-lg border border-amber-300 dark:border-amber-500/40">
  <summary class="cursor-pointer px-4 py-3 font-semibold text-amber-800 dark:text-amber-300">Correct this week's winner</summary>
  <div class="p-4">
    <p class="mb-3 text-sm text-text-secondary-light dark:text-text-secondary">Only use this to fix a grading mistake. Winners are normally set automatically.</p>
    {# existing manual winner <form> goes here, unchanged #}
  </div>
</details>
{% endif %}
```
Keep the POST handler (`family_pool_admin_winners`) and audit path unchanged.

- [ ] **Step 5: Run test + manual smoke**

Run: `python manage.py test pickem_homepage.tests.WinnersOverrideVisibilityTests --settings=pickem.test_settings`
Expected: PASS.
Manual: winners page shows auto winner read-only; owner sees the collapsible override; a correction still saves.

- [ ] **Step 6: Commit**
```bash
git add pickem/pickem_homepage/views.py pickem/pickem_homepage/templates/pickem/family_admin_winners.html pickem/pickem_homepage/tests.py
git commit -m "feat(winners): read-only auto winners with owner-only override

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 12: Superadmin family force-delete — service + audit action

**Files:**
- Modify: `pickem/pickem_superadmin/models.py:24-46` (add `Action.FAMILY_FORCE_DELETED`)
- Modify: `pickem/pickem_superadmin/services.py` (add `force_delete_family`)
- Test: `pickem/pickem_superadmin/tests/` (new/appended service test)

**Interfaces:**
- Produces: `services.force_delete_family(request, family) -> dict` (returns deleted counts). New enum `SuperAdminAuditLog.Action.FAMILY_FORCE_DELETED = 'family_force_deleted'`.

- [ ] **Step 1: Write the failing test**
```python
class ForceDeleteFamilyTests(TestCase):
    def test_cascade_deletes_related_but_keeps_users(self):
        from django.contrib.auth.models import User
        from pickem_api.models import (Family, Pool, PoolSettings, FamilyMembership,
            FamilyInvitation, FamilyAuditLog, GamePicks, userSeasonPoints)
        # Build a family with a pool, settings, a member (real User), a pick, a season row.
        # Call services.force_delete_family(request, family).
        # Assert Family/Pool/PoolSettings/membership/pick/season rows gone.
        # Assert the User still exists.
        ...
```
Use `RequestFactory` + a superuser for `request`. Assert `User.objects.filter(pk=member.pk).exists()` is True and `Family.objects.filter(pk=fam.pk).exists()` is False.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test pickem_superadmin --settings=pickem.test_settings`
Expected: FAIL — no `force_delete_family`.

- [ ] **Step 3: Add the audit action**

In `pickem/pickem_superadmin/models.py`, add to `Action`:
```python
        FAMILY_FORCE_DELETED = 'family_force_deleted', 'Family force-deleted'
```

- [ ] **Step 4: Implement the service**

Add to `pickem/pickem_superadmin/services.py`:
```python
def force_delete_family(request, family):
    """Hard-delete a family and all pool/family-scoped data. Never deletes Users.
    Related FKs are PROTECT, so rows are removed child-first inside one transaction."""
    from django.db import transaction
    from pickem_api.models import (
        Pool, PoolSettings, FamilyMembership, FamilyInvitation, FamilyAuditLog,
        GamePicks, userPoints, userSeasonPoints, userStats,
    )
    from pickem_homepage.models import (
        MessageBoardPost, MessageBoardComment, MessageBoardVote, SiteBanner,
    )

    pool_ids = list(Pool.objects.filter(family=family).values_list('id', flat=True))
    counts = {}
    with transaction.atomic():
        counts['picks'] = GamePicks.objects.filter(pool_id__in=pool_ids).delete()[0]
        counts['user_points'] = userPoints.objects.filter(pool_id__in=pool_ids).delete()[0]
        counts['season_points'] = userSeasonPoints.objects.filter(pool_id__in=pool_ids).delete()[0]
        counts['user_stats'] = userStats.objects.filter(pool_id__in=pool_ids).delete()[0]
        counts['votes'] = MessageBoardVote.objects.filter(family=family).delete()[0]
        counts['comments'] = MessageBoardComment.objects.filter(family=family).delete()[0]
        counts['posts'] = MessageBoardPost.objects.filter(family=family).delete()[0]
        counts['family_audit'] = FamilyAuditLog.objects.filter(family=family).delete()[0]
        counts['invitations'] = FamilyInvitation.objects.filter(family=family).delete()[0]
        counts['pool_settings'] = PoolSettings.objects.filter(pool_id__in=pool_ids).delete()[0]
        counts['memberships'] = FamilyMembership.objects.filter(family=family).delete()[0]
        counts['banners'] = SiteBanner.objects.filter(family=family).delete()[0]
        counts['pools'] = Pool.objects.filter(family=family).delete()[0]
        before = {'slug': family.slug, 'name': family.name, 'deleted_counts': counts}
        target_id = str(family.id)
        family.delete()
        log_action(
            request,
            action=SuperAdminAuditLog.Action.FAMILY_FORCE_DELETED,
            target=None,
            target_type='Family',
            target_id=target_id,
            summary=f"Force-deleted family {before['slug']}",
            changes={'before': before, 'after': None},
        )
    return counts
```
Note: confirm `log_action`'s signature for `target`/`target_type`/`target_id` (`pickem_superadmin/audit.py`) and match it — if `log_action` derives type/id from a `target` object, pass the pre-captured strings via whatever kwargs it exposes (the family object no longer exists post-delete, so pass strings).

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test pickem_superadmin --settings=pickem.test_settings`
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add pickem/pickem_superadmin/models.py pickem/pickem_superadmin/services.py pickem/pickem_superadmin/tests/ pickem/pickem_superadmin/migrations/
git commit -m "feat(superadmin): force_delete_family service + audit action

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
(If adding the `Action` choice generated a migration, include it. TextChoices on a CharField normally needs none — run `makemigrations pickem_superadmin` to confirm and include any output.)

---

### Task 13: Superadmin family force-delete — view, URL, template, gate test

**Files:**
- Modify: `pickem/pickem_superadmin/views/families.py` (add `family_force_delete`)
- Modify: `pickem/pickem_superadmin/views/__init__.py` (export it)
- Modify: `pickem/pickem_superadmin/urls.py` (add route)
- Modify: `pickem/pickem_superadmin/templates/superadmin/families.html` (per-row danger control)
- Test: `pickem/pickem_superadmin/tests/test_auth.py` + families view test

**Interfaces:**
- Consumes: `services.force_delete_family`.
- Produces: URL name `superadmin:family_force_delete` (`<int:family_id>`).

- [ ] **Step 1: Write the failing tests**

Add a gate test entry and a behavior test:
```python
class FamilyForceDeleteViewTests(TestCase):
    def test_slug_mismatch_aborts(self):
        # POST confirm_slug='wrong' -> family still exists, error message.
        ...
    def test_correct_slug_deletes(self):
        # POST confirm_slug=<family.slug> -> family gone, redirect to families.
        ...
    def test_requires_superadmin(self):
        # non-superuser POST -> 404.
        ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test pickem_superadmin --settings=pickem.test_settings`
Expected: FAIL — URL/view missing; `test_all_urls_are_covered` will also flag the new URL once added.

- [ ] **Step 3: Add the view**

In `pickem/pickem_superadmin/views/families.py`:
```python
from django.shortcuts import get_object_or_404
from pickem_superadmin import services

@superadmin_required
@require_POST
def family_force_delete(request, family_id):
    family = get_object_or_404(Family, id=family_id)
    confirm = (request.POST.get('confirm_slug') or '').strip()
    if confirm != family.slug:
        messages.error(request, f'Confirmation did not match. Type "{family.slug}" exactly to delete.')
        return redirect('superadmin:families')
    services.force_delete_family(request, family)
    messages.success(request, f'Family "{family.slug}" and all related data were deleted.')
    return redirect('superadmin:families')
```

- [ ] **Step 4: Export + route**

In `pickem/pickem_superadmin/views/__init__.py`, import `family_force_delete` from `.families` and add it to `__all__`. In `pickem/pickem_superadmin/urls.py` add:
```python
    path('families/<int:family_id>/force-delete/', views.family_force_delete, name='family_force_delete'),
```

- [ ] **Step 5: Template danger control**

In `superadmin/families.html`, add a per-row danger control that reveals a confirm form:
```html
<details class="mt-2">
  <summary class="cursor-pointer text-[12px] font-semibold text-red-700">Delete family…</summary>
  <form method="post" action="{% url 'superadmin:family_force_delete' row.family.id %}" class="mt-2 flex items-center gap-2">
    {% csrf_token %}
    <span class="text-[12px] text-[#667085]">Type <code>{{ row.family.slug }}</code> to confirm ({{ row.member_count }} members, {{ row.pool_count }} pools):</span>
    <input type="text" name="confirm_slug" class="sa-input w-48 !py-1" autocomplete="off">
    <button type="submit" class="rounded bg-red-600 px-3 py-1 text-[12px] font-semibold text-white">Delete</button>
  </form>
</details>
```
(The `families` view already annotates `member_count` and `pool_count`.)

- [ ] **Step 6: Run tests to verify pass**

Run: `python manage.py test pickem_superadmin --settings=pickem.test_settings`
Expected: PASS (including `test_all_urls_are_covered`).

- [ ] **Step 7: Commit**
```bash
git add pickem/pickem_superadmin/views/families.py pickem/pickem_superadmin/views/__init__.py pickem/pickem_superadmin/urls.py pickem/pickem_superadmin/templates/superadmin/families.html pickem/pickem_superadmin/tests/
git commit -m "feat(superadmin): force-delete family view with slug confirm

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 14: Superadmin nav reorder (audit last)

**Files:**
- Modify: `pickem/pickem_superadmin/templates/superadmin/base.html:37-41`
- Test: `pickem/pickem_superadmin/tests/` (append render-order assertion)

- [ ] **Step 1: Write the failing test**
```python
def test_nav_order_jobs_logs_audit(self):
    from django.test import Client
    from django.contrib.auth.models import User
    User.objects.create_superuser('navadmin', 'nav@x.com', 'pw')
    c = Client(); c.force_login(User.objects.get(username='navadmin'))
    html = c.get('/superadmin/').content.decode()
    self.assertLess(html.index('>jobs<'), html.index('>logs<'))
    self.assertLess(html.index('>logs<'), html.index('>audit<'))
```
(Place in a superadmin nav/overview test class.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test pickem_superadmin --settings=pickem.test_settings`
Expected: FAIL — current order is jobs, audit, logs.

- [ ] **Step 3: Reorder the nav**

In `superadmin/base.html`, move the `audit` `<a>` (line ~39) to AFTER the `logs` `<a>` (line ~41), so the order is `jobs`, `logs`, `audit`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test pickem_superadmin --settings=pickem.test_settings`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add pickem/pickem_superadmin/templates/superadmin/base.html pickem/pickem_superadmin/tests/
git commit -m "chore(superadmin): nav order jobs, logs, audit

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 15: Superadmin email page — column alignment (visual)

**Files:**
- Modify: `pickem/pickem_superadmin/templates/superadmin/email.html:6-7,135`

**Interfaces:** none (layout only; no unit test — verify in browser).

- [ ] **Step 1: Reproduce**

Load `http://localhost:8000/superadmin/email/` at desktop width (≥1024px). Observe the left column (provider/campaign cards) vs the right "Current status" card and note exactly how they fail to line up (likely the two grid columns don't share a top edge, or the conditionally-`hidden` provider card shifts the stack).

- [ ] **Step 2: Fix the grid alignment**

Apply the minimal CSS fix in `email.html`. Most likely: add `items-start` to the grid container (line 6) so both columns align to the top, and ensure the right card (`<div class="sa-card p-4">` at line 135) is a direct grid child at the same level as the left `<div class="space-y-4">` wrapper (line 7). If the misalignment is caused by the hidden provider card leaving whitespace, confirm `hidden` fully removes it (it does) and that the campaign card is the first visible left item. Adjust so first cards of both columns start at the same Y.

- [ ] **Step 3: Verify visually**

Reload the page in light and dark at the `lg` breakpoint and just above/below 1024px. Confirm the left and right column top edges line up. Capture a screenshot for the review.

- [ ] **Step 4: Commit**
```bash
git add pickem/pickem_superadmin/templates/superadmin/email.html
git commit -m "fix(superadmin): align email page columns on desktop

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 16: Create-family page visual polish (frontend-design)

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/create_family.html`
- Test: `pickem/pickem_homepage/tests.py` (guard: fields still present)

**Interfaces:** none new — presentation only. No form/field/name changes.

- [ ] **Step 1: Load the design skill**

Invoke `frontend-design` (`Skill` tool) for aesthetic direction before editing. Keep every existing form field, `name`, and validation intact.

- [ ] **Step 2: Write a regression guard test**
```python
class CreateFamilyRenderTests(TestCase):
    def test_form_fields_still_present(self):
        from django.test import Client
        from django.contrib.auth.models import User
        u = User.objects.create_user('cf', 'cf@x.com', 'pw')
        c = Client(); c.force_login(u)
        html = c.get('/families/create/').content.decode()
        for needed in ('family_name', 'pool_name', 'picks_lock_mode', 'name="entry_fee_amount"'):
            self.assertIn(needed, html)
```

- [ ] **Step 3: Run test to verify current pass (baseline)**

Run: `python manage.py test pickem_homepage.tests.CreateFamilyRenderTests --settings=pickem.test_settings`
Expected: PASS now (guards against regressions during the redesign).

- [ ] **Step 4: Polish the template**

Improve hero/intro, section grouping, spacing, input consistency, and light/dark treatment per the frontend-design guidance. Do not rename fields or change the form action. Re-run the guard test after editing:
Run: `python manage.py test pickem_homepage.tests.CreateFamilyRenderTests --settings=pickem.test_settings`
Expected: PASS.

- [ ] **Step 5: Verify visually + commit**

Load `http://localhost:8000/families/create/`, confirm the flow still submits, then:
```bash
git add pickem/pickem_homepage/templates/pickem/create_family.html pickem/pickem_homepage/tests.py
git commit -m "style(create-family): visual polish, no field changes

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 17: Full suite + final verification

- [ ] **Step 1: Run the complete test suite**

Run: `python manage.py test --settings=pickem.test_settings`
Expected: PASS (note the known 3F+2E postgres `--keepdb` artifact from memory does not apply under `test_settings`/CI; if seen, re-run without `--keepdb`).

- [ ] **Step 2: Manual walkthrough**

In the browser, exercise: settings pick-locking dropdown, picks page lock behavior, locked-pool invites (form hidden), payout visibility, banner icon dropdowns, batch invites, winners read-only+override, superadmin pools lock column, email alignment, families force-delete (on throwaway test data), nav order, create-family page.

- [ ] **Step 3: Final commit if any touch-ups**
```bash
git add -A && git commit -m "chore: final verification touch-ups for nits batch

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Reusable test setup recipe

Several tasks above say "reuse existing helpers." Use this exact pattern — it
mirrors `PostLoginTenantRoutingTests` (`pickem_homepage/tests.py:143-170`). Copy
the helpers into each new `TestCase` (or subclass a small mixin):

```python
from django.test import Client, TestCase
from django.contrib.auth.models import User
from pickem_api.models import Family, Pool, PoolSettings, FamilyMembership

class _TenantMixin:
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("owner", "owner@x.com", "pass")
        self.newbie = User.objects.create_user("newbie", "newbie@x.com", "pass")

    def _family_with_pool(self, name="Fam", slug="fam", season=2526):
        family = Family.objects.create(name=name, slug=slug)
        pool = Pool.objects.create(
            family=family, name="Main", slug="main",
            season=season, competition="nfl", is_default=True,
        )
        return family, pool

    def _settings(self, pool, **kw):
        return PoolSettings.objects.create(pool=pool, **kw)

    def _member(self, user, family, role=FamilyMembership.Role.MEMBER):
        return FamilyMembership.objects.create(
            family=family, user=user, role=role,
            status=FamilyMembership.Status.ACTIVE,
        )
```

**Forcing "entries locked"** (Tasks 6, 7): set
`late_join_policy=PoolSettings.LateJoinPolicy.LOCK_AFTER_WEEK_1` on the pool
settings AND patch the week-complete check (it is imported inside
`pool_entries_locked`, so patch it at its source):

```python
from unittest.mock import patch

with patch("pickem_api.weekly_winners.week_is_complete", return_value=True):
    # ... perform the POST / call accept_invitation_for_user here ...
```

So the Task 6 test body is: build owner + `_family_with_pool` + `_settings(pool,
late_join_policy=LOCK_AFTER_WEEK_1)`, `_member(self.owner, family, OWNER)`,
`force_login(self.owner)`, then under the patch POST to
`reverse('family_pool_admin_invites', args=[family.slug, pool.slug])` with a
recipient email; assert `FamilyInvitation.objects.count() == 0`.

The Task 7 test body is: same locked setup, create a valid invitation via the
existing `create_admin_invitation(...)` helper (family, pool, actor=self.owner,
role=MEMBER, recipient_email='', expires_in_days=14, request=<RequestFactory
request with self.owner>), then under the patch call
`accept_invitation_for_user(request_for(self.newbie), raw_code)` and assert the
4th return value equals `ENTRIES_LOCKED_MESSAGE` and no membership exists for
`self.newbie`.

## Notes for the implementer
- The picks-lock rename (Tasks 1–5) is the only cross-cutting change; do those in order first. Everything after is independent and can be reordered.
- The `...` in a few test stubs above is shorthand for "arrange with the recipe
  in this section, then assert as the surrounding prose describes" — replace it
  with the concrete helper calls; never commit a literal `...`.
- Templates: prefer minimal, focused diffs; match the surrounding Tailwind class conventions (`text-text-dark dark:text-white`, `sa-card`, etc.).
