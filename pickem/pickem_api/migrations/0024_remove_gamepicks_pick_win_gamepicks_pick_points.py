# Generated by Django 4.0.2 on 2022-08-28 18:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0023_remove_gamepicks_pick_points_gamepicks_pick_win'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='gamepicks',
            name='pick_win',
        ),
        migrations.AddField(
            model_name='gamepicks',
            name='pick_points',
            field=models.IntegerField(default=0),
        ),
    ]