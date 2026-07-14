# Team Logo Contrast Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-editable `Teams.logo_contrast_preset` setting and use it to render readable team logos on team-color backgrounds across the picks and scores branded team tiles.

**Architecture:** Extend the `Teams` model with a small preset enum, expose it in Django admin, and centralize branded-logo presentation data in template tags so templates consume one rendering contract instead of team-specific slug hacks. Update the branded tiles in picks and scores to use that shared contract, then cover the behavior with model/template tests.

**Tech Stack:** Django models, migrations, Django admin, custom template tags, Django templates, Django test suite.

---

## File Structure

- Modify: `pickem/pickem_api/models.py`
  Add the `Teams.LogoContrastPreset` choices and `logo_contrast_preset` field.
- Create: `pickem/pickem_api/migrations/0081_teams_logo_contrast_preset.py`
  Persist the new field with a safe default.
- Modify: `pickem/pickem_api/admin.py`
  Expose the preset in Django admin with useful list/detail visibility.
- Modify: `pickem/pickem_homepage/templatetags/pickem_homepage_extras.py`
  Add one shared helper/filter that returns branded tile presentation data: colors, preset, background style, logo classes, and burst/reverse booleans.
- Modify: `pickem/pickem_homepage/templates/pickem/picks.html`
  Replace the Jets-only logo treatment and inline gradient duplication with the shared branded-logo presentation contract for submitted/unsubmitted/edit states.
- Modify: `pickem/pickem_homepage/templates/pickem/scores.html`
  Apply the same shared branded-logo presentation contract to all score-card team-color panels.
- Modify: `pickem/pickem_api/tests.py`
  Add model/admin-focused tests for the new field default and choices.
- Modify: `pickem/pickem_homepage/tests.py`
  Add rendering tests covering the shared presentation hook and at least one branded tile output.

### Task 1: Add the Team Preset Model Field

**Files:**
- Modify: `pickem/pickem_api/models.py`
- Create: `pickem/pickem_api/migrations/0081_teams_logo_contrast_preset.py`
- Test: `pickem/pickem_api/tests.py`

- [ ] **Step 1: Write the failing model test**

```python
class TeamsLogoContrastPresetTest(TestCase):
    def test_team_logo_contrast_preset_defaults_to_default(self):
        team = Teams.objects.create(
            id=9901,
            teamNameSlug="rams",
            teamNameName="Los Angeles Rams",
        )

        self.assertEqual(
            team.logo_contrast_preset,
            Teams.LogoContrastPreset.DEFAULT,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && cd pickem && python manage.py test pickem_api.tests.TeamsLogoContrastPresetTest --settings=pickem.test_settings --verbosity=2`

Expected: `AttributeError` or model field failure because `logo_contrast_preset` and `LogoContrastPreset` do not exist yet.

- [ ] **Step 3: Write the minimal model implementation**

```python
class Teams(models.Model):
    class LogoContrastPreset(models.TextChoices):
        DEFAULT = 'default', 'Default'
        REVERSE_GRADIENT = 'reverse-gradient', 'Reverse gradient'
        WHITE_BURST = 'white-burst', 'White burst'

    id = models.IntegerField(primary_key=True)
    gameseason = models.IntegerField(blank=True, null=True)
    teamNameSlug = models.CharField(max_length=250, db_column='teamnameslug')
    teamNameName = models.CharField(max_length=250, db_column='teamnamename')
    teamLogo = models.CharField(max_length=250, blank=True, null=True, db_column='teamlogo')
    teamWins = models.IntegerField(default=0, db_column='teamwins')
    teamLosses = models.IntegerField(default=0, db_column='teamlosses')
    teamTies = models.IntegerField(default=0, db_column='teamties')
    color = models.CharField(max_length=6, blank=True, null=True)
    alternateColor = models.CharField(max_length=6, blank=True, null=True, db_column='alternatecolor')
    logo_contrast_preset = models.CharField(
        max_length=32,
        choices=LogoContrastPreset.choices,
        default=LogoContrastPreset.DEFAULT,
        help_text="Contrast treatment for logos displayed on team-color backgrounds.",
    )
```

Migration content:

```python
class Migration(migrations.Migration):
    dependencies = [
        ('pickem_api', '0080_gamepicks_auto_pick'),
    ]

    operations = [
        migrations.AddField(
            model_name='teams',
            name='logo_contrast_preset',
            field=models.CharField(
                choices=[
                    ('default', 'Default'),
                    ('reverse-gradient', 'Reverse gradient'),
                    ('white-burst', 'White burst'),
                ],
                default='default',
                help_text='Contrast treatment for logos displayed on team-color backgrounds.',
                max_length=32,
            ),
        ),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source venv/bin/activate && cd pickem && python manage.py test pickem_api.tests.TeamsLogoContrastPresetTest --settings=pickem.test_settings --verbosity=2`

Expected: PASS for the new default-field test.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/models.py pickem/pickem_api/migrations/0081_teams_logo_contrast_preset.py pickem/pickem_api/tests.py
git commit -m "feat: add team logo contrast presets"
```

### Task 2: Expose the Preset in Django Admin

**Files:**
- Modify: `pickem/pickem_api/admin.py`
- Test: `pickem/pickem_api/tests.py`

- [ ] **Step 1: Write the failing admin test**

```python
class TeamsAdminConfigurationTest(TestCase):
    def test_teams_admin_exposes_logo_contrast_preset(self):
        admin_site = AdminSite()
        admin_obj = TeamsAdmin(Teams, admin_site)

        self.assertIn('logo_contrast_preset', admin_obj.list_display)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && cd pickem && python manage.py test pickem_api.tests.TeamsAdminConfigurationTest --settings=pickem.test_settings --verbosity=2`

Expected: FAIL because the admin does not include the new field yet.

- [ ] **Step 3: Update the admin registration**

```python
@admin.register(Teams)
class TeamsAdmin(admin.ModelAdmin):
    list_display = (
        'teamNameSlug',
        'teamNameName',
        'teamWins',
        'teamLosses',
        'teamTies',
        'color',
        'alternateColor',
        'logo_contrast_preset',
    )
    list_filter = ('logo_contrast_preset',)
    search_fields = ('teamNameSlug', 'teamNameName')
    fields = (
        'id',
        'gameseason',
        'teamNameSlug',
        'teamNameName',
        'teamLogo',
        'teamWins',
        'teamLosses',
        'teamTies',
        'color',
        'alternateColor',
        'logo_contrast_preset',
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source venv/bin/activate && cd pickem && python manage.py test pickem_api.tests.TeamsAdminConfigurationTest --settings=pickem.test_settings --verbosity=2`

Expected: PASS for the admin configuration assertion.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/admin.py pickem/pickem_api/tests.py
git commit -m "feat: expose logo contrast presets in team admin"
```

### Task 3: Centralize Branded Logo Presentation Data

**Files:**
- Modify: `pickem/pickem_homepage/templatetags/pickem_homepage_extras.py`
- Test: `pickem/pickem_homepage/tests.py`

- [ ] **Step 1: Write the failing template-tag test**

```python
class TeamBrandPresentationFilterTests(TestCase):
    def test_team_brand_presentation_respects_reverse_gradient_and_white_burst(self):
        reverse_team = Teams.objects.create(
            id=9101,
            teamNameSlug="rams",
            teamNameName="Los Angeles Rams",
            color="003594",
            alternateColor="FFA300",
            logo_contrast_preset=Teams.LogoContrastPreset.REVERSE_GRADIENT,
        )
        burst_team = Teams.objects.create(
            id=9102,
            teamNameSlug="jets",
            teamNameName="New York Jets",
            color="125740",
            alternateColor="ffffff",
            logo_contrast_preset=Teams.LogoContrastPreset.WHITE_BURST,
        )

        reverse_data = team_brand_presentation(reverse_team)
        burst_data = team_brand_presentation(burst_team)

        self.assertIn("#00359440", reverse_data["background_style"])
        self.assertIn("#FFA300", reverse_data["background_style"])
        self.assertFalse(reverse_data["show_white_burst"])
        self.assertTrue(burst_data["show_white_burst"])
        self.assertIn("drop-shadow", burst_data["logo_style"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && cd pickem && python manage.py test pickem_homepage.tests.TeamBrandPresentationFilterTests --settings=pickem.test_settings --verbosity=2`

Expected: FAIL because the shared helper does not exist.

- [ ] **Step 3: Implement the helper/filter**

```python
def build_team_brand_presentation(team):
    base_color = (getattr(team, 'color', None) or '333333').strip('#')
    alt_color = (getattr(team, 'alternateColor', None) or '666666').strip('#')
    preset = getattr(team, 'logo_contrast_preset', Teams.LogoContrastPreset.DEFAULT)

    gradient_start = alt_color
    gradient_end = base_color
    if preset == Teams.LogoContrastPreset.REVERSE_GRADIENT:
        gradient_start, gradient_end = base_color, alt_color

    show_white_burst = preset == Teams.LogoContrastPreset.WHITE_BURST
    logo_style = ''
    if show_white_burst:
        logo_style = 'filter: drop-shadow(0 0 6px rgba(255,255,255,0.9));'

    return {
        'preset': preset,
        'background_style': (
            f'background: linear-gradient(135deg, '
            f'#{gradient_start}40 0%, '
            f'#{gradient_end} 50%, '
            f'#{gradient_end} 100%);'
        ),
        'show_white_burst': show_white_burst,
        'logo_style': logo_style,
    }


@register.filter
def team_brand_presentation(team):
    return build_team_brand_presentation(team)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source venv/bin/activate && cd pickem && python manage.py test pickem_homepage.tests.TeamBrandPresentationFilterTests --settings=pickem.test_settings --verbosity=2`

Expected: PASS for reverse-gradient and white-burst behavior.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/templatetags/pickem_homepage_extras.py pickem/pickem_homepage/tests.py
git commit -m "feat: centralize team brand logo presentation"
```

### Task 4: Apply the Shared Presentation Contract to Picks

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/picks.html`
- Test: `pickem/pickem_homepage/tests.py`

- [ ] **Step 1: Write the failing picks template test**

```python
def test_picks_template_uses_team_brand_presentation_for_branded_logo_tiles(self):
    response = self.client.get(self._tenant_url("family_pool_picks"))

    self.assertContains(response, "|team_brand_presentation")
    self.assertContains(response, "show_white_burst")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && cd pickem && python manage.py test pickem_homepage.tests.PicksPageRenderingTests --settings=pickem.test_settings --verbosity=2`

Expected: FAIL because the picks template still hard-codes gradients and the Jets-only drop-shadow.

- [ ] **Step 3: Update the branded picks tiles**

```django
{% with game.awayTeamSlug|lookuplogo as logo_url %}
{% with team|team_brand_presentation as team_brand %}
<div class="relative h-[100px] flex items-center justify-center py-2"
     style="{{ team_brand.background_style }}">
    {% if team_brand.show_white_burst %}
    <div class="absolute inset-0 flex items-center justify-center">
        <div class="h-16 w-16 rounded-full bg-white/85 blur-md"></div>
    </div>
    {% endif %}
    <img src="{{ logo_url.teamLogo|default:'/static/images/nfl.svg' }}"
         alt="{{ game.awayTeamName }} logo"
         class="w-16 h-16 object-contain drop-shadow-lg relative z-10"
         {% if team_brand.logo_style %}style="{{ team_brand.logo_style }}"{% endif %}>
</div>
{% endwith %}
{% endwith %}
```

Also update the edit modal JavaScript data contract so it carries `data-away-preset` and `data-home-preset`, then computes the preview gradient/burst from the same preset rules instead of the Jets slug special-case.

- [ ] **Step 4: Run test to verify it passes**

Run: `source venv/bin/activate && cd pickem && python manage.py test pickem_homepage.tests.PicksPageRenderingTests --settings=pickem.test_settings --verbosity=2`

Expected: PASS with the picks template using shared presentation hooks.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/templates/pickem/picks.html pickem/pickem_homepage/tests.py
git commit -m "feat: apply logo contrast presets on picks tiles"
```

### Task 5: Apply the Shared Presentation Contract to Scores

**Files:**
- Modify: `pickem/pickem_homepage/templates/pickem/scores.html`
- Test: `pickem/pickem_homepage/tests.py`

- [ ] **Step 1: Write the failing scores template test**

```python
def test_scores_template_uses_team_brand_presentation_for_branded_logo_tiles(self):
    response = self.client.get(self._tenant_url("family_pool_scores"))

    self.assertContains(response, "show_white_burst")
    self.assertContains(response, "background_style")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && cd pickem && python manage.py test pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests --settings=pickem.test_settings --verbosity=2`

Expected: FAIL because the scores tiles are still hand-built.

- [ ] **Step 3: Update the scores branded logo panels**

```django
{% with game.homeTeamSlug|lookuplogo as home_team %}
{% with home_team|team_brand_presentation as home_brand %}
<div class="relative ..." style="{{ home_brand.background_style }}">
    {% if home_brand.show_white_burst %}
    <div class="absolute inset-0 flex items-center justify-center">
        <div class="h-16 w-16 rounded-full bg-white/85 blur-md"></div>
    </div>
    {% endif %}
    <img src="{{ home_team.teamLogo|default:'/static/images/nfl.svg' }}"
         alt="{{ game.homeTeamName }} logo"
         class="relative z-10 ..."
         {% if home_brand.logo_style %}style="{{ home_brand.logo_style }}"{% endif %}>
</div>
{% endwith %}
{% endwith %}
```

Apply the same pattern to away-team branded score panels so picks and scores share the same contrast logic.

- [ ] **Step 4: Run test to verify it passes**

Run: `source venv/bin/activate && cd pickem && python manage.py test pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests --settings=pickem.test_settings --verbosity=2`

Expected: PASS with the branded scores panels rendering the preset hooks.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_homepage/templates/pickem/scores.html pickem/pickem_homepage/tests.py
git commit -m "feat: apply logo contrast presets on score tiles"
```

### Task 6: End-to-End Verification and Cleanup

**Files:**
- Modify: `pickem/pickem_api/tests.py`
- Modify: `pickem/pickem_homepage/tests.py`

- [ ] **Step 1: Run the focused regression suite**

Run:

```bash
source venv/bin/activate && cd pickem && python manage.py test \
  pickem_api.tests.TeamsLogoContrastPresetTest \
  pickem_api.tests.TeamsAdminConfigurationTest \
  pickem_homepage.tests.TeamBrandPresentationFilterTests \
  pickem_homepage.tests.PicksPageRenderingTests \
  pickem_homepage.tests.TenantProfilesPlayersMessageBoardIsolationTests \
  --settings=pickem.test_settings --verbosity=2
```

Expected: PASS across the new model/admin/template coverage.

- [ ] **Step 2: Run diff hygiene**

Run: `git diff --check`

Expected: no whitespace or patch-format issues.

- [ ] **Step 3: Run the broader app suite touched by the feature**

Run:

```bash
source venv/bin/activate && cd pickem && python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=1
```

Expected: PASS for the homepage and API suites after the rendering and model changes.

- [ ] **Step 4: Review the final changed files**

Run:

```bash
git diff -- pickem/pickem_api/models.py \
  pickem/pickem_api/admin.py \
  pickem/pickem_homepage/templatetags/pickem_homepage_extras.py \
  pickem/pickem_homepage/templates/pickem/picks.html \
  pickem/pickem_homepage/templates/pickem/scores.html \
  pickem/pickem_api/tests.py \
  pickem/pickem_homepage/tests.py
```

Expected: changes are limited to the contrast preset feature and do not touch unrelated in-progress command work.

- [ ] **Step 5: Commit**

```bash
git add pickem/pickem_api/models.py \
  pickem/pickem_api/admin.py \
  pickem/pickem_api/migrations/0081_teams_logo_contrast_preset.py \
  pickem/pickem_homepage/templatetags/pickem_homepage_extras.py \
  pickem/pickem_homepage/templates/pickem/picks.html \
  pickem/pickem_homepage/templates/pickem/scores.html \
  pickem/pickem_api/tests.py \
  pickem/pickem_homepage/tests.py
git commit -m "feat: add admin-controlled team logo contrast presets"
```

## Self-Review

- Spec coverage:
  - Admin-editable preset: covered in Tasks 1-2.
  - Shared rendering path: covered in Task 3.
  - Picks and scores branded tiles: covered in Tasks 4-5.
  - Regression coverage: covered in Tasks 1-6.
  - Superadmin follow-up: intentionally left as `TODO.md`, not implementation scope.
- Placeholder scan:
  - No `TODO`, `TBD`, or “implement later” placeholders remain in the execution tasks.
- Type consistency:
  - Uses one field name consistently: `logo_contrast_preset`.
  - Uses one enum class consistently: `Teams.LogoContrastPreset`.
  - Uses one shared helper/filter contract consistently: `team_brand_presentation`.
