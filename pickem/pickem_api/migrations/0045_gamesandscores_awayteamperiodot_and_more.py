# Generated by Django 4.0.2 on 2022-09-19 02:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0044_gamepicks_tiebreakeryards'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamesandscores',
            name='awayTeamPeriodOT',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='gamesandscores',
            name='homeTeamPeriodOT',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
