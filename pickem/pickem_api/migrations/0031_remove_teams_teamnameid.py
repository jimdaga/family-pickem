# Generated by Django 4.0.2 on 2022-09-06 03:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0030_teams_teamlosses_teams_teamwins'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='teams',
            name='teamNameId',
        ),
    ]
