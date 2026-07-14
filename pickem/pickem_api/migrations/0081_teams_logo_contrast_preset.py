from django.db import migrations, models


def seed_logo_contrast_presets(apps, schema_editor):
    Teams = apps.get_model('pickem_api', 'Teams')
    Teams.objects.filter(teamNameSlug='rams').update(
        logo_contrast_preset='reverse-gradient',
    )
    Teams.objects.filter(teamNameSlug='jets').update(
        logo_contrast_preset='white-burst',
    )


def unseed_logo_contrast_presets(apps, schema_editor):
    Teams = apps.get_model('pickem_api', 'Teams')
    Teams.objects.filter(teamNameSlug__in=['rams', 'jets']).update(
        logo_contrast_preset='default',
    )


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
                help_text='Controls the admin-selected logo contrast treatment for scorecards and other branded surfaces.',
                max_length=32,
            ),
        ),
        migrations.RunPython(
            seed_logo_contrast_presets,
            unseed_logo_contrast_presets,
        ),
    ]
