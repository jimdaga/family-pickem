from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pickem_homepage', '0009_publication_slots_by_source'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aiweeklysummaryrun',
            name='publication',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='ai_summary_runs', to='pickem_homepage.familypublication',
            ),
        ),
    ]
