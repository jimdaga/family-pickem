# Generated by Django 4.0.2 on 2022-08-31 01:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0025_remove_gamepicks_pick_points_gamepicks_pick_correct'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gamepicks',
            name='id',
            field=models.CharField(max_length=250, primary_key=True, serialize=False),
        ),
    ]