# Generated manually to add recommendation_candidate FK.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recommendation", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("matchcard", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="matchcard",
            name="recommendation_candidate",
            field=models.ForeignKey(
                blank=True,
                db_column="recommendation_candidate_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="match_cards",
                to="recommendation.recommendationcandidate",
            ),
        ),
        migrations.AddIndex(
            model_name="matchcard",
            index=models.Index(
                fields=["recommendation_candidate"],
                name="match_card_rec_cand_idx",
            ),
        ),
    ]
