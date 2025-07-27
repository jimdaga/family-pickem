# Generated manually for adding betting odds, weather, and venue fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0065_userstats_perfectweeksseason_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamesandscores',
            name='homeTeamWinProbability',
            field=models.FloatField(blank=True, help_text='Home team win probability as percentage (0-100)', null=True),
        ),
        migrations.AddField(
            model_name='gamesandscores',
            name='awayTeamWinProbability',
            field=models.FloatField(blank=True, help_text='Away team win probability as percentage (0-100)', null=True),
        ),
        migrations.AddField(
            model_name='gamesandscores',
            name='spread',
            field=models.FloatField(blank=True, help_text='Point spread (positive favors home team)', null=True),
        ),
        migrations.AddField(
            model_name='gamesandscores',
            name='overUnder',
            field=models.FloatField(blank=True, help_text='Over/under total points line', null=True),
        ),
        migrations.AddField(
            model_name='gamesandscores',
            name='temperature',
            field=models.IntegerField(blank=True, help_text='Game temperature in Fahrenheit', null=True),
        ),
        migrations.AddField(
            model_name='gamesandscores',
            name='weatherCondition',
            field=models.CharField(blank=True, help_text='Weather condition description', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='gamesandscores',
            name='venueIndoor',
            field=models.BooleanField(default=False, help_text='Whether the game is played indoors'),
        ),
    ] 