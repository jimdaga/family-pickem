# Generated by Django 4.0.2 on 2022-08-20 01:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0005_gamesandscores_delete_schedule'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamesandscores',
            name='gameyear',
            field=models.CharField(default=2022, max_length=4),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='gameWeek',
            field=models.CharField(max_length=2),
        ),
        migrations.AlterField(
            model_name='gamesandscores',
            name='id',
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
    ]