# Generated by Django 4.0.2 on 2022-08-17 03:38

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('team_home', models.CharField(max_length=200)),
                ('team_away', models.CharField(max_length=200)),
                ('game_date', models.DateTimeField(verbose_name='date of game')),
            ],
        ),
    ]
