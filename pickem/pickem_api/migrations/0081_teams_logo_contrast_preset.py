from django.db import migrations, models


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
    ]
