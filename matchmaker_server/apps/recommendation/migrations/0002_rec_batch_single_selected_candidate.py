from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recommendation", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="recommendationcandidate",
            constraint=models.UniqueConstraint(
                fields=("batch",),
                condition=models.Q(("is_selected", True)),
                name="rec_batch_single_selected_candidate",
            ),
        ),
    ]
