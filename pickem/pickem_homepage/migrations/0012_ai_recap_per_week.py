from django.db import migrations, models


def backfill_recap_weeks(apps, schema_editor):
    """Stamp each existing AI recap with the week it was last generated for.

    Until now a pool had a single AI row that every week overwrote, so its
    body is the most recent successful run's week.
    """
    FamilyPublication = apps.get_model('pickem_homepage', 'FamilyPublication')
    AIWeeklySummaryRun = apps.get_model('pickem_homepage', 'AIWeeklySummaryRun')
    for publication in FamilyPublication.objects.filter(source='ai_weekly_summary'):
        run = (
            AIWeeklySummaryRun.objects.filter(publication=publication, status='success')
            .order_by('-created_at').first()
        )
        if run is not None:
            publication.season, publication.week = run.season, run.week
            publication.save(update_fields=['season', 'week'])


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_homepage', '0011_alter_familypublication_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='familypublication',
            name='season',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='familypublication',
            name='week',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_recap_weeks, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='familypublication',
            name='one_publication_per_pool_source',
        ),
        migrations.AddConstraint(
            model_name='familypublication',
            constraint=models.UniqueConstraint(
                condition=models.Q(source='commissioner'), fields=('pool', 'source'),
                name='one_commissioner_publication_per_pool',
            ),
        ),
        migrations.AddConstraint(
            model_name='familypublication',
            constraint=models.UniqueConstraint(
                condition=models.Q(source='ai_weekly_summary'), fields=('pool', 'source', 'season', 'week'),
                name='one_ai_recap_per_pool_week',
            ),
        ),
    ]
