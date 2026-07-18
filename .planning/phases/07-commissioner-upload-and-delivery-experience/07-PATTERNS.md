# Phase 7: Commissioner Upload and Delivery Experience - Pattern Map

**Mapped:** 2026-07-18  
**Files analyzed:** 8 anticipated modified/created files  
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `package.json`, `package-lock.json` | config/dependency | build-time asset | existing root Tailwind dependency declaration | role-match |
| `pickem/pickem_homepage/forms.py` | form/validation | request-response | `FamilyAdminSettingsForm` | exact |
| `pickem/pickem_homepage/views.py` | controller | tenant CRUD + file I/O | `family_pool_admin_settings` | exact |
| `pickem/pickem_homepage/templates/pickem/family_admin_settings.html` | component + inline controller | local event-driven state + multipart submit | existing logo field plus deactivation IIFE | exact for page/form; role-match for JS |
| `pickem/pickem_homepage/static/.../family-logo-editor.js` (if extracted) | browser controller | local event-driven transform | template IIFE at `family_admin_settings.html` | role-match |
| `pickem/pickem_homepage/templates/pickem/family_picker.html` | component | controlled asset render | its two existing logo/button variants | exact |
| `pickem/pickem_homepage/templates/pickem/family_pool_home.html` | component | controlled asset render | lobby hero logo block | exact |
| `pickem/pickem_homepage/tests.py` | integration/form/template tests | request-response + file-I/O | `FamilyLogoUploadFoundationTests`, `FamilyAdminSettingsFormTests` | exact |

## Pattern Assignments

### `pickem/pickem_homepage/forms.py` (form validation, request-response)

**Analog:** `FamilyAdminSettingsForm`, lines 224-257.

Keep fields declared directly on the existing form, use its `ADMIN_TEXT_INPUT_CLASSES`, and use Django `clean()`/`add_error()` rather than parsing crop input in the view. The existing upload widget provides the accessibility pattern to extend:

```python
logo = forms.FileField(
    label="Family logo",
    required=False,
    widget=forms.ClearableFileInput(attrs={
        'class': ADMIN_TEXT_INPUT_CLASSES,
        'accept': 'image/jpeg,image/png,image/webp',
        'aria-describedby': 'family-logo-help family-logo-error',
    }),
)
```

Add `crop_x`, `crop_y`, `crop_width`, `crop_height` as optional integer-compatible hidden inputs and `remove_logo` as a boolean field here. The form must enforce all-or-none crop values and mutual exclusion (`logo` wins/clears removal at the UI, but a tampered POST must be handled deliberately). Pass only a strict `{x, y, width, height}` mapping to the existing processor; do not clamp or normalize untrusted values in the view.

### `pickem/pickem_homepage/views.py` (tenant controller, multipart CRUD/file-I/O)

**Analog:** `family_pool_admin_settings`, lines 1301-1430.

Preserve the complete existing control flow: family-admin decorator, POST/FILES binding, upload-handler error handoff, row locks, atomic block, standard `messages` redirect, audit record, and compensating storage cleanup. The critical seams are:

```python
@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_pool_admin_settings(request, family_slug, pool_slug):
    ...
    form = FamilyAdminSettingsForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        initial=initial,
    )
    ...
    with transaction.atomic():
        locked_family = Family.objects.select_for_update().get(id=family.id)
```

When there is an uploaded file, change only the existing processor call to supply form-cleaned crop data:

```python
processed_logo = process_family_logo(
    form.cleaned_data['logo'], form.cleaned_data['crop_data']
)
```

For staged removal, copy the existing update/audit/compensation structure rather than adding an endpoint: clear the locked model field only after a valid POST; record `before_present`/`after_present`; redirect with `Settings updated.`. A processor validation error must retain its existing early `render()` behavior (lines 1347-1364), preserving non-file inputs and the old server reference. Do not call `FieldFile.delete()` as a Phase 7 shortcut: object lifecycle is explicitly deferred to Phase 8.

### `pickem/pickem_homepage/templates/pickem/family_admin_settings.html` (settings component + browser editor)

**Analog:** current logo markup, lines 63-82; native page IIFE, lines 267-281.

Reuse the current multipart form and neutral rounded-square thumbnail as the editor's non-JavaScript baseline:

```django
<form method="post" enctype="multipart/form-data" ...>
    {% csrf_token %}
    ...
    <div class="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-lg
                border border-border-light bg-gray-50 dark:border-border-subtle dark:bg-bg-dark">
        {% if family.logo %}
        <img src="{{ family.logo.url }}" alt="{{ family.name }} logo" class="h-full w-full object-contain">
        {% else %}
        <img src="{% static 'images/familypickem.png' %}" alt="Family Pick'em default logo" class="h-full w-full object-contain">
        {% endif %}
    </div>
```

The only established page-JS pattern is a guarded self-contained IIFE:

```javascript
(function () {
    var input = document.getElementById('confirm-family-name');
    var button = document.getElementById('deactivate-family-button');
    if (!input || !button) return;
    input.addEventListener('input', function () { ... });
})();
```

Use this guarded, page-specific pattern (or an equivalent static module loaded only by this template) for Cropper initialization. Add stable `data-*` hooks/IDs for: native chooser, current/default preview, local editor image, slider, Reset, Clear selection, Remove logo, four hidden crop inputs, and `remove_logo`. The no-JS markup must remain usable: absent hidden crop values means the established centered server crop. On image selection, make a local `URL.createObjectURL`; revoke it before replacing/clearing it and on `pagehide`. Do not serialize the object URL. The submit handler should write source-pixel integer coordinates only; it must never canvas-export or upload separately.

Use native `window.confirm` for the exact staged removal wording, then set hidden `remove_logo`, clear file/crop state, and show the static default. Selecting a file must reverse staged removal. Clearing a selected file must restore the old server-controlled image/default without issuing a mutation.

### `pickem/pickem_api/logo_processing.py` (existing canonical transform contract)

**Analog:** `process_family_logo`, lines 78-130 and `validate_square_crop`, lines 38-62.

Phase 7 should not duplicate image handling. The source of truth for hidden-input names/shape is:

```python
crop_box = (
    _center_square_box(normalized.size)
    if crop_data is None
    else validate_square_crop(crop_data, normalized.size)
)
```

The client form contract is exact: decimal integer strings for `x`, `y`, `width`, `height`; a positive bounded square; or all fields absent. Since the processor applies `ImageOps.exif_transpose()` (line 102), cropper coordinates must be from an orientation-normalized preview. If that mapping cannot be demonstrated for an EXIF-rotated file, clear the crop fields so the server deliberately selects the centered crop instead of submitting mismatched values.

### `pickem/pickem_homepage/templates/pickem/family_picker.html` (controlled render component)

**Analog:** lines 45-50 and 87-92.

There are two currently duplicated picker button variants (member and superadmin). Replace both with the same compact wrapper/source/fallback contract. Current source selection is already correct in principle:

```django
{% if choice.family.logo %}{{ choice.family.logo.url }}{% else %}{% static 'images/logo.png' %}{% endif %}
```

But the current `rounded-full`, `object-cover`, and name-repeating `alt` are Phase 7 targets. Wrap the image in a neutral `h-8 w-8 overflow-hidden rounded-lg` frame; use `object-contain` and `alt="" aria-hidden="true"` because visible sibling text identifies the family. Use the same static fallback asset selected for the setting/lobby contract (research calls out the existing inconsistency between `logo.png` and `familypickem.png`).

### `pickem/pickem_homepage/templates/pickem/family_pool_home.html` (controlled render component)

**Analog:** lobby hero, lines 24-40.

The logo is immediately beside the visible `{{ family.name }} Lobby` heading, so change its current name-repeating alt text to decorative semantics and give the image/fallback the same neutral rounded-square wrapper as the picker. Keep the server-controlled branches only:

```django
{% if family.logo %}
<img src="{{ family.logo.url }}" ...>
{% else %}
<img src="{% static 'images/logo.png' %}" ...>
{% endif %}
```

Do not pass user filenames, browser blob URLs, or any original upload reference to the template.

### `pickem/pickem_homepage/tests.py` (Django integration/form/template tests)

**Analogs:** `FamilyLogoUploadFoundationTests`, lines 6627-6694; `FamilyAdminSettingsFormTests`, lines 6697 onward; `FamilyAdminExperienceTests._settings_url()`/`_default_scoring_fields()`, lines 3962-3995.

Extend the Phase 6 test class to retain its temporary `FileSystemStorage` swap and image fixture:

```python
field = Family._meta.get_field('logo')
self._previous_logo_storage = field.storage
field.storage = FileSystemStorage(location=self._logo_storage_tmp.name)
self.addCleanup(setattr, field, 'storage', self._previous_logo_storage)
```

Use its existing authenticated settings POST shape, with `family_name`, `pool_name`, `**self._default_scoring_fields()`, file, and crop/remove fields. Cover: valid coordinates produce the canonical WebP; partial/malformed/non-square/out-of-bounds fields preserve the old reference and render an error; absent crop fields retain centered behavior; confirmed-form `remove_logo` clears only the DB reference on redirect/audits; a selected upload plus removal tampering has defined mutually-exclusive form behavior; and invalid images preserve ordinary bound values plus old logo.

For render assertions, follow lines 6676-6680 (`assertContains`/`assertNotContains`) and GET picker/lobby routes as existing family-experience tests do. Assert hidden field/editor hooks, multipart form, no `logo_url`, canonical-or-static sources only, compact `rounded-lg` wrappers, and decorative empty alt strings. There is no established JavaScript unit-test harness in `package.json`; keep browser state behavior in browser UAT/manual verification unless the implementation explicitly introduces a test harness.

### `package.json` and `package-lock.json` (dependency/build configuration)

**Analog:** root `package.json`, lines 1-27.

The repository declares frontend build dependencies at the root and builds Tailwind from `pickem/pickem_homepage/static/css/input.css` to `tailwind.css`. Add the researched, pinned/locked `cropperjs` dependency through the package manager so `package-lock.json` remains synchronized; do not introduce a CDN script into the template. The implementation must choose an asset import/build path compatible with the current no-JavaScript-bundler setup (for example, copy/build a vetted local vendor asset through an explicit npm script). The CSS must be included deliberately alongside existing Tailwind output; do not rely on an undocumented global asset.

## Shared Patterns

### Tenant authorization and safe mutation

**Source:** `pickem/pickem_homepage/views.py:1301-1429`.

Every server mutation remains on the existing `@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)` route and uses locked rows plus `transaction.atomic()`. Phase 7 must not add a separate crop/upload endpoint, direct browser S3 upload, or a client-controlled asset URL.

### Validation and safe error return

**Source:** `pickem/pickem_homepage/forms.py:224-257`, `pickem/pickem_homepage/views.py:1321-1364`, `pickem/pickem_api/logo_processing.py:28-62`.

Use form validation to form the crop mapping, processor validation as final authority, and the existing bound-form render route for errors. Never repopulate a browser `File` after a failed POST; leave regular fields bound and render the prior saved/default asset.

### Asset rendering and accessibility

**Source:** `pickem/pickem_api/models.py:55-73`, `pickem/pickem_api/storage.py:6-16`, current setting/picker/lobby templates.

`Family.logo` is a private-storage, generated WebP field. Render only its `.url` or a `{% static %}` default. Use a neutral rounded-square `overflow-hidden` frame and `object-contain` consistently; where a visible adjacent family name exists, use `alt="" aria-hidden="true"`.

### Browser-local state lifecycle

**Source:** no exact editor analog; closest local code is the guarded settings-page IIFE at `family_admin_settings.html:267-281`.

Keep `saved`, `selected-file`, and `remove-staged` states mutually exclusive. Browser state is strictly ephemeral: object URL and Cropper instance are created only after selection and cleaned up on reset/replacement/clear/pagehide. The server sees only the original multipart file, four strict crop fields, and optional removal boolean at the existing Save submit point.
