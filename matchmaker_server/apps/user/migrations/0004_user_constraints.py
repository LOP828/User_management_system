# Generated manually for the MVP scaffold.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0003_user_indexes"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="customerprofile",
            constraint=models.CheckConstraint(
                condition=models.Q(("gender__in", ["male", "female"])),
                name="customer_profile_gender_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="customerprofile",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "pool_status__in",
                        [
                            "new_pending",
                            "communicated_pending_recommend",
                            "recommended_pending_select",
                            "selected_pending_meet",
                            "met_not_continue",
                            "paused",
                        ],
                    )
                ),
                name="customer_profile_pool_status_valid",
            ),
        ),
    ]
