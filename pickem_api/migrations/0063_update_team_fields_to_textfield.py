# Generated manually for team field updates

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0062_add_userprofile_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userstats',
            name='leastPickedSeason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='leastPickedTotal',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='mostPickedSeason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='userstats',
            name='mostPickedTotal',
            field=models.TextField(blank=True, null=True),
        ),
    ] 