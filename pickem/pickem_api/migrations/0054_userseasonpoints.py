# Generated by Django 4.0.2 on 2023-08-29 03:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_api', '0053_delete_seasonpoints'),
    ]

    operations = [
        migrations.CreateModel(
            name='userSeasonPoints',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('userEmail', models.EmailField(blank=True, max_length=254)),
                ('userID', models.CharField(blank=True, max_length=250)),
                ('gameyear', models.CharField(blank=True, max_length=4)),
                ('gameseason', models.IntegerField(blank=True, null=True)),
                ('week_1_points', models.IntegerField(blank=True, null=True)),
                ('week_1_bonus', models.IntegerField(blank=True, null=True)),
                ('week_1_winner', models.BooleanField(blank=True, default=False)),
                ('week_2_points', models.IntegerField(blank=True, null=True)),
                ('week_2_bonus', models.IntegerField(blank=True, null=True)),
                ('week_2_winner', models.BooleanField(blank=True, default=False)),
                ('week_3_points', models.IntegerField(blank=True, null=True)),
                ('week_3_bonus', models.IntegerField(blank=True, null=True)),
                ('week_3_winner', models.BooleanField(blank=True, default=False)),
                ('week_4_points', models.IntegerField(blank=True, null=True)),
                ('week_4_bonus', models.IntegerField(blank=True, null=True)),
                ('week_4_winner', models.BooleanField(blank=True, default=False)),
                ('week_5_points', models.IntegerField(blank=True, null=True)),
                ('week_5_bonus', models.IntegerField(blank=True, null=True)),
                ('week_5_winner', models.BooleanField(blank=True, default=False)),
                ('week_6_points', models.IntegerField(blank=True, null=True)),
                ('week_6_bonus', models.IntegerField(blank=True, null=True)),
                ('week_6_winner', models.BooleanField(blank=True, default=False)),
                ('week_7_points', models.IntegerField(blank=True, null=True)),
                ('week_7_bonus', models.IntegerField(blank=True, null=True)),
                ('week_7_winner', models.BooleanField(blank=True, default=False)),
                ('week_8_points', models.IntegerField(blank=True, null=True)),
                ('week_8_bonus', models.IntegerField(blank=True, null=True)),
                ('week_8_winner', models.BooleanField(blank=True, default=False)),
                ('week_9_points', models.IntegerField(blank=True, null=True)),
                ('week_9_bonus', models.IntegerField(blank=True, null=True)),
                ('week_9_winner', models.BooleanField(blank=True, default=False)),
                ('week_10_points', models.IntegerField(blank=True, null=True)),
                ('week_10_bonus', models.IntegerField(blank=True, null=True)),
                ('week_10_winner', models.BooleanField(blank=True, default=False)),
                ('week_11_points', models.IntegerField(blank=True, null=True)),
                ('week_11_bonus', models.IntegerField(blank=True, null=True)),
                ('week_11_winner', models.BooleanField(blank=True, default=False)),
                ('week_12_points', models.IntegerField(blank=True, null=True)),
                ('week_12_bonus', models.IntegerField(blank=True, null=True)),
                ('week_12_winner', models.BooleanField(blank=True, default=False)),
                ('week_13_points', models.IntegerField(blank=True, null=True)),
                ('week_13_bonus', models.IntegerField(blank=True, null=True)),
                ('week_13_winner', models.BooleanField(blank=True, default=False)),
                ('week_14_points', models.IntegerField(blank=True, null=True)),
                ('week_14_bonus', models.IntegerField(blank=True, null=True)),
                ('week_14_winner', models.BooleanField(blank=True, default=False)),
                ('week_15_points', models.IntegerField(blank=True, null=True)),
                ('week_15_bonus', models.IntegerField(blank=True, null=True)),
                ('week_15_winner', models.BooleanField(blank=True, default=False)),
                ('week_16_points', models.IntegerField(blank=True, null=True)),
                ('week_16_bonus', models.IntegerField(blank=True, null=True)),
                ('week_16_winner', models.BooleanField(blank=True, default=False)),
                ('week_17_points', models.IntegerField(blank=True, null=True)),
                ('week_17_bonus', models.IntegerField(blank=True, null=True)),
                ('week_17_winner', models.BooleanField(blank=True, default=False)),
                ('week_18_points', models.IntegerField(blank=True, null=True)),
                ('week_18_bonus', models.IntegerField(blank=True, null=True)),
                ('week_18_winner', models.BooleanField(blank=True, default=False)),
                ('total_points', models.IntegerField(blank=True, null=True)),
                ('year_winner', models.BooleanField(blank=True, default=False)),
                ('playerAdded', models.DateTimeField(auto_now_add=True)),
                ('playerUpdated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['total_points'],
            },
        ),
    ]