# Generated by Django 4.0.2 on 2025-07-21 02:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0060_alter_userstats_correctpicktotalseason_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='currentSeason',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('season', models.IntegerField(blank=True, null=True)),
            ],
        ),
    ]
