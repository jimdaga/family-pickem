"""Shared save loop for superadmin "matrix" pages — dense tables where every
row is a separately-prefixed ModelForm bound from one big POST.

Pools (Task 5), families (Task 6), and teams (Task 7) all share this exact
shape: bind a row form per object, skip rows that weren't on the submitted
page, reject stale rows under optimistic concurrency, diff the ones that
validate, save only what actually changed, and let the caller do its own
audit write (the right target/model differs per matrix, so logging stays
with the caller instead of being baked in here).
"""
from django.db import transaction

from pickem_superadmin.audit import diff_fields


def save_matrix(request, *, objects, form_class, tracked_fields, key_field,
                 on_save, stale_check=True):
    """Bind a prefixed row form per object, save changed rows, return (saved, failed, stale).

    - objects: iterable of model instances (each has .pk; the form is bound with
      prefix=str(obj.pk))
    - form_class: a ModelForm bound per row as
      form_class(request.POST, instance=obj, prefix=str(obj.pk))
    - tracked_fields: tuple of field names to diff for the audit changes dict
    - key_field: a field name whose presence in POST (as f"{pk}-{key_field}")
      signals "this row was on the submitted page"; rows absent from POST are
      skipped
    - on_save(obj, changes): called after a successful save inside the same
      transaction, so the caller does its own log_action() with the right
      audit target and dual-write
    - stale_check: when True, the row carries f"{pk}-updated_at" and the save is
      rejected (added to `stale`) if it != obj.updated_at.isoformat(); when
      False, skip the concurrency check entirely (some models, e.g. Teams,
      have no updated_at column)

    Returns (saved:int, failed:list, stale:list) — failed/stale hold the
    original objects (not strings), so the caller can build whatever message
    text it wants (e.g. "family.slug/pool.slug") from the object's own
    relations. Per-row transaction.atomic around save+on_save. A row with no
    diff is skipped (not counted as saved). An invalid form adds the object to
    `failed`. A stale row adds the object to `stale`.
    """
    saved = 0
    failed = []
    stale = []

    for obj in objects:
        prefix = str(obj.pk)
        if f'{prefix}-{key_field}' not in request.POST:
            continue  # row not on the submitted page (filtered out)

        if stale_check:
            # Optimistic concurrency: the row carries the updated_at it was
            # rendered with. If the DB moved on, someone else saved while
            # this page was open.
            submitted_stamp = request.POST.get(f'{prefix}-updated_at', '')
            if submitted_stamp != obj.updated_at.isoformat():
                stale.append(obj)
                continue

        before = {f: getattr(obj, f) for f in tracked_fields}
        form = form_class(request.POST, instance=obj, prefix=prefix)
        if not form.is_valid():
            failed.append(obj)
            continue

        after = {f: form.cleaned_data[f] for f in tracked_fields}
        changes = diff_fields(before, after)
        if not changes:
            continue  # no diff — skip, not counted as saved

        with transaction.atomic():
            form.save()
            on_save(obj, changes)
        saved += 1

    return saved, failed, stale
