# Generated by Django 4.0.2 on 2022-08-23 01:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0014_alter_gameweeks_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gameweeks',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]