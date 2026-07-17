"""Rename pools still carrying the old season-embedded default name.

The old default was "NFL Pick'em - 20XX - 20YY" (the pool's own season baked
into the name), which every header then doubled by appending display_season
and competition again — "NFL Pick'em - 2026 - 2027 - 2026-2027 NFL". The
default is now "Pick'em Pool"; this renames only pools whose name exactly
matches the old default for their own season, so any commissioner-customized
name is left alone.

The reverse is a no-op: the forward pass doesn't record which rows it
changed, so a real reversal would clobber every pool legitimately named
"Pick'em Pool" (including ones created after this migration ran).
"""

from django.db import migrations

NEW_DEFAULT_NAME = "Pick'em Pool"


def old_default_name(season):
    season_str = str(season or "").zfill(4)
    if len(season_str) == 4 and season_str.isdigit():
        return f"NFL Pick'em - 20{season_str[:2]} - 20{season_str[2:]}"
    return None


def rename_default_pools(apps, schema_editor):
    Pool = apps.get_model('pickem_api', 'Pool')
    for pool in Pool.objects.filter(name__startswith="NFL Pick'em - "):
        if pool.name == old_default_name(pool.season):
            pool.name = NEW_DEFAULT_NAME
            pool.save(update_fields=['name', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0088_family_status_audit_action'),
    ]

    operations = [
        migrations.RunPython(rename_default_pools, migrations.RunPython.noop),
    ]
