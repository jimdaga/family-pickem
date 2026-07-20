from django.db import migrations, models


def keep_latest_slot_per_source(apps, schema_editor):
    """Retain the currently published item, otherwise the most recently edited.

    Earlier versions allowed unlimited drafts.  The new explicit two-slot
    model needs a deterministic one-time consolidation before its constraint.
    """
    Publication = apps.get_model('pickem_homepage', 'FamilyPublication')
    seen = set()
    for publication in Publication.objects.order_by(
        'pool_id', 'source', '-is_published', '-updated_at', '-id'
    ):
        key = (publication.pool_id, publication.source)
        if key in seen:
            publication.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('pickem_homepage', '0008_aiweeklysummaryrun'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='familypublication',
            name='one_published_publication_per_pool',
        ),
        migrations.RunPython(keep_latest_slot_per_source, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='familypublication',
            constraint=models.UniqueConstraint(
                fields=('pool', 'source'), name='one_publication_per_pool_source',
            ),
        ),
    ]
