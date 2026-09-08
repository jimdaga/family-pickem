# Commissioner Lobby Setup Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show pool commissioners a getting-started card near the top of the lobby — invite players, pool settings, post a lobby note — visible only until the season's first game kicks off.

**Architecture:** The lobby view (`family_pool_home`) computes one boolean, `show_commissioner_setup`, from the viewer's membership role and the season's earliest kickoff. The template renders a single `{% if %}` block styled with the existing `.commissioner-message-card` classes, so no new CSS frame is invented.

**Tech Stack:** Django 5.2 templates and views, Tailwind CSS (compiled from `static/css/input.css`), `django.test.TestCase` + `Client`, Python 3.12, run with `uv`.

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-09-07-commissioner-lobby-setup-card-design.md`.
- Working directory for test/manage commands is `/Users/jim/git/family-pickem/pickem`; `npm` and `git` run from the repo root `/Users/jim/git/family-pickem`.
- Branch `feat/commissioner-lobby-setup` already exists and is checked out. Do not create another.
- **Never** append a `?v=...` cache-buster to a `{% static %}` URL. In production `{% static %}` returns an S3 querystring-signed URL; a second `?` corrupts the signature and the whole site renders unstyled. This has regressed twice.
- `static/css/tailwind.css` is committed and served. Any Tailwind utility class used in a template must already exist in it, or the stylesheet must be rebuilt with `npm run build:prod` and committed.
- Commissioner test is `membership.role in ('owner', 'admin')` — the same expression the existing OWNER ACTIONS block uses. Do not introduce a new permission helper.
- Run tests with: `uv run python manage.py test <label> --settings=pickem.test_settings`
- Every commit message ends with:
  ```text
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EKQvoUBZ6qDWj5YsRS8nY7
  ```

## File Structure

- **Modify** `pickem/pickem_homepage/views.py` — in `family_pool_home` (starts line 1117), compute `season_kickoff` / `show_commissioner_setup` and add the latter to the context dict (currently lines 1262-1283).
- **Modify** `pickem/pickem_homepage/templates/pickem/family_pool_home.html` — insert the card between the action grid (ends line 153) and the publications loop (starts line 155).
- **Modify** `pickem/pickem_homepage/tests.py` — new `CommissionerSetupCardTests` class appended at the end.
- **Possibly modify** `pickem/pickem_homepage/static/css/tailwind.css` — only if Task 2 introduces an uncompiled utility class; rebuilt via `npm run build:prod`, never hand-edited.

---

### Task 1: View flag

**Files:**
- Modify: `pickem/pickem_homepage/views.py` (inside `family_pool_home`, which begins at line 1117)
- Test: `pickem/pickem_homepage/tests.py`

**Interfaces:**
- Consumes: `pickem_api.models.GamesAndScores`, `FamilyMembership.Role`, `django.utils.timezone`.
- Produces: context key `show_commissioner_setup` (bool) on the `family_pool_home` template context.

**Background for the implementer:**

`family_pool_home` already resolves `gameseason` and `current_competition` near
its top (lines 1121-1122) and builds one big `context` dict at the end. The
viewer's membership is `tenant_context.membership`, already passed to the
template as `membership`.

Two traps:

- There is an existing `season_has_started` local in this view (line 1137). It
  means "some game has been *scored*", which flips hours after kickoff. Do not
  reuse it — this feature keys on the first game *starting*.
- `membership` can be `None`. The superuser god-mode path enters with a
  synthetic owner membership, but defensive code must not assume an object.

`FamilyMembership.Role` values are `'owner'`, `'admin'`, `'member'`
(`pickem_api/models.py:160`).

- [ ] **Step 1: Write the failing tests**

Append to `pickem/pickem_homepage/tests.py`:

```python
class CommissionerSetupCardTests(TestCase):
    """The pre-season commissioner getting-started card on the lobby."""

    @classmethod
    def setUpTestData(cls):
        Site.objects.get_or_create(
            id=1, defaults={"domain": "testserver", "name": "testserver"}
        )
        currentSeason.objects.get_or_create(
            season=2526, defaults={"display_name": "2025-2026"}
        )

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            "setup-owner", email="setup-owner@example.com", password="pass"
        )
        self.member = User.objects.create_user(
            "setup-member", email="setup-member@example.com", password="pass"
        )
        self.family = Family.objects.create(name="Setup Family", slug="setup-family")
        self.pool = Pool.objects.create(
            family=self.family,
            name="Main Pickem",
            slug="setup-main",
            season=2526,
            competition="nfl",
            status=Pool.Status.ACTIVE,
            is_default=True,
        )
        PoolSettings.objects.create(pool=self.pool)
        FamilyMembership.objects.create(
            family=self.family,
            user=self.owner,
            role=FamilyMembership.Role.OWNER,
            status=FamilyMembership.Status.ACTIVE,
        )
        FamilyMembership.objects.create(
            family=self.family,
            user=self.member,
            role=FamilyMembership.Role.MEMBER,
            status=FamilyMembership.Status.ACTIVE,
        )

    def _lobby(self):
        return self.client.get(
            reverse(
                "family_pool_home",
                kwargs={
                    "family_slug": self.family.slug,
                    "pool_slug": self.pool.slug,
                },
            )
        )

    def _game(self, game_id, kickoff, week="1"):
        return GamesAndScores.objects.create(
            id=game_id,
            slug=f"setup-game-{game_id}",
            competition="nfl",
            gameWeek=week,
            gameyear="2025",
            gameseason=2526,
            startTimestamp=kickoff,
            statusType="notstarted",
            statusTitle="Scheduled",
            homeTeamId=1,
            homeTeamSlug="atl",
            homeTeamName="Atlanta Falcons",
            awayTeamId=2,
            awayTeamSlug="ari",
            awayTeamName="Arizona Cardinals",
        )

    def test_owner_sees_flag_before_first_kickoff(self):
        self._game(9001, timezone.now() + timedelta(days=3))
        self.client.force_login(self.owner)

        self.assertTrue(self._lobby().context["show_commissioner_setup"])

    def test_member_never_sees_flag(self):
        self._game(9001, timezone.now() + timedelta(days=3))
        self.client.force_login(self.member)

        self.assertFalse(self._lobby().context["show_commissioner_setup"])

    def test_owner_loses_flag_once_first_game_has_kicked_off(self):
        # Week 1 already started; a later week is still in the future. The
        # earliest kickoff of the SEASON is what counts, not this week's.
        self._game(9001, timezone.now() - timedelta(hours=1))
        self._game(9002, timezone.now() + timedelta(days=6), week="2")
        self.client.force_login(self.owner)

        self.assertFalse(self._lobby().context["show_commissioner_setup"])

    def test_owner_sees_flag_when_season_has_no_games_yet(self):
        self.client.force_login(self.owner)

        self.assertTrue(self._lobby().context["show_commissioner_setup"])

    def test_other_competition_kickoff_does_not_close_the_window(self):
        past = self._game(9003, timezone.now() - timedelta(hours=1))
        GamesAndScores.objects.filter(id=past.id).update(competition="ncaa")
        self._game(9001, timezone.now() + timedelta(days=3))
        self.client.force_login(self.owner)

        self.assertTrue(self._lobby().context["show_commissioner_setup"])
```

If any of `Family`, `Pool`, `PoolSettings`, `FamilyMembership`, `GamesAndScores`,
`currentSeason`, `Site`, `User`, `Client`, `reverse`, `timezone`, `timedelta` is
not already imported at the top of `tests.py`, add it. Check first — most are
already there for the existing suites.

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run python manage.py test pickem_homepage.tests.CommissionerSetupCardTests --settings=pickem.test_settings
```
Expected: FAIL, 5 tests — `KeyError: 'show_commissioner_setup'`.

- [ ] **Step 3: Compute the flag in the view**

In `pickem/pickem_homepage/views.py`, inside `family_pool_home`, immediately
before the `context = {` dict, add:

```python
    # Commissioner getting-started card: pool setup links that only matter
    # before anyone has played a game. Keyed on the season's first KICKOFF, not
    # the `season_has_started` local above -- that one means "a game has been
    # scored", which flips hours later. No games loaded yet is the deep
    # pre-season, so the card shows then too.
    season_kickoff = (
        GamesAndScores.objects.filter(
            gameseason=gameseason,
            competition=current_competition,
        )
        .order_by('startTimestamp')
        .values_list('startTimestamp', flat=True)
        .first()
    )
    viewer_membership = tenant_context.membership
    show_commissioner_setup = bool(
        viewer_membership
        and viewer_membership.role in (
            FamilyMembership.Role.OWNER,
            FamilyMembership.Role.ADMIN,
        )
        and (season_kickoff is None or timezone.now() < season_kickoff)
    )
```

Then add to the `context` dict, next to `'membership'`:

```python
        'show_commissioner_setup': show_commissioner_setup,
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
uv run python manage.py test pickem_homepage.tests.CommissionerSetupCardTests --settings=pickem.test_settings
```
Expected: PASS, 5 tests.

If `FamilyMembership` or `timezone` is not already imported in `views.py`, add
the import — both are very likely present already.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/views.py pickem/pickem_homepage/tests.py
git commit -m "$(cat <<'EOF'
feat(lobby): flag the pre-season commissioner setup window

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EKQvoUBZ6qDWj5YsRS8nY7
EOF
)"
```

---

### Task 2: The card itself

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/family_pool_home.html` (insert between line 153 and line 155)
- Test: `pickem/pickem_homepage/tests.py` (extend `CommissionerSetupCardTests`)

**Interfaces:**
- Consumes: `show_commissioner_setup`, `family`, `pool` from the Task 1 context.
- Produces: a block marked `data-testid="commissioner-setup"`.

**Background for the implementer:**

The insertion point is between the closing `</div>` of `lobby-action-grid` and
the `{% if publications %}` line.

The visual frame is **not** new CSS. `.commissioner-message-card` and
`.commissioner-message-card__inner` already exist in `static/css/input.css`
(lines 931-987) and are already compiled into `tailwind.css`. They are the same
construction as the AI recap card — animated conic-gradient border, soft inner
gradient, texture overlay — in navy/sky/teal rather than purple/magenta, with
light and dark variants and a `prefers-reduced-motion` opt-out. Reuse them, plus
`.commissioner-message-badge` for the pill.

Two structural rules the existing cards follow, which this must match:

1. The animated border lives on the outer element; **all content goes inside the
   `__inner` div**, or it will be painted over by the gradient.
2. Add `lobby-section` to the outer element so the card joins the GSAP
   scroll-reveal that runs over `.lobby-section` (template line ~623).

- [ ] **Step 1: Write the failing tests**

Append these methods to `CommissionerSetupCardTests` in `pickem_homepage/tests.py`:

```python
    def test_card_renders_for_owner_with_all_three_links(self):
        self._game(9001, timezone.now() + timedelta(days=3))
        self.client.force_login(self.owner)

        page = self._lobby()

        self.assertContains(page, 'data-testid="commissioner-setup"')
        for route in (
            "family_pool_admin_invites",
            "family_pool_admin_settings",
            "family_pool_admin_publications",
        ):
            self.assertContains(
                page,
                reverse(
                    route,
                    kwargs={
                        "family_slug": self.family.slug,
                        "pool_slug": self.pool.slug,
                    },
                ),
            )

    def test_card_absent_for_member(self):
        self._game(9001, timezone.now() + timedelta(days=3))
        self.client.force_login(self.member)

        self.assertNotContains(self._lobby(), 'data-testid="commissioner-setup"')

    def test_card_absent_after_kickoff(self):
        self._game(9001, timezone.now() - timedelta(hours=1))
        self.client.force_login(self.owner)

        self.assertNotContains(self._lobby(), 'data-testid="commissioner-setup"')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run python manage.py test pickem_homepage.tests.CommissionerSetupCardTests --settings=pickem.test_settings
```
Expected: FAIL — `test_card_renders_for_owner_with_all_three_links` cannot find
`data-testid="commissioner-setup"`. The two absence tests pass trivially.

- [ ] **Step 3: Insert the card markup**

In `pickem/pickem_homepage/templates/pickem/family_pool_home.html`, between the
action grid's closing `</div>` and `{% if publications %}`:

```html
    <!-- ═══════════════════════ COMMISSIONER GETTING STARTED ══════════════════════ -->
    {% if show_commissioner_setup %}
    <div class="commissioner-message-card lobby-section mb-6" data-testid="commissioner-setup">
        <div class="commissioner-message-card__inner">
            <div class="flex items-center gap-2">
                <span class="flex h-7 w-7 items-center justify-center rounded-full bg-primary/15 text-primary" aria-hidden="true">
                    <i class="fas fa-flag-checkered text-xs"></i>
                </span>
                <div>
                    <div class="flex flex-wrap items-center gap-2">
                        <h3 class="text-lg font-bold text-text-dark dark:text-white">Get your pool ready</h3>
                        <span class="commissioner-message-badge">Getting started</span>
                    </div>
                    <p class="text-xs text-text-secondary-light dark:text-text-secondary">Only you can see this. It disappears once the season kicks off.</p>
                </div>
            </div>

            <div class="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                <a href="{% url 'family_pool_admin_invites' family.slug pool.slug %}"
                   class="group flex items-start gap-3 rounded-xl border border-border-light dark:border-border-subtle bg-surface-light dark:bg-surface px-4 py-3 hover:border-primary dark:hover:border-primary transition-colors">
                    <i class="fas fa-ticket-alt mt-0.5 text-primary" aria-hidden="true"></i>
                    <span>
                        <span class="block text-sm font-bold text-text-dark dark:text-white">Invite other players</span>
                        <span class="block text-xs text-text-secondary-light dark:text-text-secondary">Send join links to your league</span>
                    </span>
                </a>
                <a href="{% url 'family_pool_admin_settings' family.slug pool.slug %}"
                   class="group flex items-start gap-3 rounded-xl border border-border-light dark:border-border-subtle bg-surface-light dark:bg-surface px-4 py-3 hover:border-primary dark:hover:border-primary transition-colors">
                    <i class="fas fa-sliders mt-0.5 text-primary" aria-hidden="true"></i>
                    <span>
                        <span class="block text-sm font-bold text-text-dark dark:text-white">Pool settings</span>
                        <span class="block text-xs text-text-secondary-light dark:text-text-secondary">Scoring, pick locking, missed picks</span>
                    </span>
                </a>
                <a href="{% url 'family_pool_admin_publications' family.slug pool.slug %}"
                   class="group flex items-start gap-3 rounded-xl border border-border-light dark:border-border-subtle bg-surface-light dark:bg-surface px-4 py-3 hover:border-primary dark:hover:border-primary transition-colors">
                    <i class="fas fa-bullhorn mt-0.5 text-primary" aria-hidden="true"></i>
                    <span>
                        <span class="block text-sm font-bold text-text-dark dark:text-white">Post a lobby note</span>
                        <span class="block text-xs text-text-secondary-light dark:text-text-secondary">Welcome everyone to the season</span>
                    </span>
                </a>
            </div>
        </div>
    </div>
    {% endif %}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
uv run python manage.py test pickem_homepage.tests.CommissionerSetupCardTests --settings=pickem.test_settings
```
Expected: PASS, 8 tests.

- [ ] **Step 5: Rebuild Tailwind if the markup introduced a new utility**

Every utility above is common in this template already, but verify rather than
assume. From the repo root, check the committed stylesheet for the two least
common ones:

```bash
grep -c 'mt-0\.5' pickem/pickem_homepage/static/css/tailwind.css
grep -c 'sm\\:grid-cols-3' pickem/pickem_homepage/static/css/tailwind.css
```

If either prints `0`, rebuild and commit the stylesheet:

```bash
npm run build:prod
```

Do not hand-edit `tailwind.css`, and do not add a `?v=` cache-buster anywhere.

- [ ] **Step 6: Commit**

```bash
git add pickem/pickem_homepage/templates/pickem/family_pool_home.html \
        pickem/pickem_homepage/tests.py
# add only if step 5 actually rebuilt it:
# git add pickem/pickem_homepage/static/css/tailwind.css
git commit -m "$(cat <<'EOF'
feat(lobby): add commissioner getting-started card

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EKQvoUBZ6qDWj5YsRS8nY7
EOF
)"
```

---

### Task 3: Verify in the running app and across the suite

**Files:** none modified unless a problem is found.

**Interfaces:**
- Consumes: everything above.
- Produces: nothing.

- [ ] **Step 1: Run the full test suite**

Run:
```bash
uv run python manage.py test --settings=pickem.test_settings
```
Expected: PASS. The lobby template is shared by many existing tests, so a
regression here shows up immediately.

- [ ] **Step 2: Confirm the card renders in the real page**

The dev server is assumed to be running at `http://localhost:8000` — do not
start one. Fetch a lobby page as a logged-in commissioner and confirm the block
is in the HTML:

```bash
curl -s http://localhost:8000/ | head -20
```

If the local database's current season is already underway, the card is
correctly absent and there is nothing to see; say so rather than forcing it.
The suite in Task 1/2 is the authority on the behaviour.

- [ ] **Step 3: Commit any fix**

Only if Step 1 or 2 turned up a problem. Otherwise there is nothing to commit
and the branch is ready.

---

## Notes for review

- The card duplicates the existing "Manage Invites" button in the OWNER ACTIONS
  row at the bottom of the lobby. That button is left alone: it stays useful
  after kickoff, when this card is gone.

---

## Amendments made during review

The plan above is the pre-implementation record. Three of its steps were
superseded by review findings before merge; the shipped code differs as follows.

- **The role test now runs before the kickoff query** (Task 1, Step 3). As
  planned, `season_kickoff` was computed unconditionally, so every plain member
  paid for a query whose result was discarded. The final code resolves the role
  first and queries only for an owner or admin.
- **The gate uses `role_allows(..., FamilyMembership.Role.ADMIN)`**, not the
  hand-written `role in ('owner', 'admin')` tuple the constraints section
  specified. That keeps it in lockstep with the `ROLE_ORDER` hierarchy the three
  linked admin pages already enforce.
- **The kickoff query scopes to `pool.competition`**, not the
  `current_competition` the plan used. `current_competition` comes from today's
  `GameWeeks` row (falling back to `'nfl'`), so it describes the site's current
  slate rather than this pool's; where the two disagree the card would show or
  hide on the wrong signal.
- **Coverage added** for the `ADMIN` role, the superuser god-mode path, and the
  `pool.competition` scoping. The link assertions are scoped to the card element
  because the invites URL also renders in the OWNER ACTIONS strip lower down the
  lobby, where a page-wide assertion would pass with the card's own link deleted.
- **Manual verification** (Task 3, Step 2) used an authenticated Django test
  client against the real local database rather than the bare
  `curl http://localhost:8000/` the plan suggested, which sends no session
  cookie and requests the site root — it could not have verified a
  commissioner-only card.
