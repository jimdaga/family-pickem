# Generated by Django 4.0.2 on 2024-10-25 03:07

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0057_userstats_pickpercentseason'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userstats',
            name='id',
            field=models.CharField(default=uuid.uuid4, editable=False, max_length=250, primary_key=True, serialize=False),
        ),
    ]
