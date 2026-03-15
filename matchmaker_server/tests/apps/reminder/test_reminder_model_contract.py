import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.reminder.models import Reminder


pytestmark = pytest.mark.django_db


def test_reminder_meta_contract():
    assert Reminder._meta.db_table == "reminder"
    assert Reminder._meta.get_field("status").default == Reminder.STATUS_PENDING
    assert Reminder._meta.get_field("is_manual").default is False
    assert Reminder._meta.get_field("processed_at").null is True
    assert Reminder._meta.get_field("processed_at").blank is True
    assert Reminder._meta.get_field("staff").target_field.name == "id"


def test_reminder_allows_minimal_required_fields(create_staff):
    staff = create_staff()

    reminder = Reminder.objects.create(
        target_type=Reminder.TARGET_USER,
        target_id=1,
        staff=staff,
        remind_type=Reminder.TYPE_FOLLOWUP_TIMEOUT,
        remind_at=timezone.now(),
    )

    assert reminder.status == Reminder.STATUS_PENDING
    assert reminder.processed_at is None
    assert reminder.is_manual is False


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("target_type", "unknown_target"),
        ("remind_type", "unknown_type"),
        ("status", "unknown_status"),
    ],
)
def test_reminder_db_constraints_reject_invalid_enum_values(create_staff, field_name, field_value):
    staff = create_staff()
    payload = {
        "target_type": Reminder.TARGET_USER,
        "target_id": 1,
        "staff": staff,
        "remind_type": Reminder.TYPE_MATCHED_REVISIT,
        "remind_at": timezone.now(),
        "status": Reminder.STATUS_PENDING,
    }
    payload[field_name] = field_value

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Reminder.objects.create(**payload)
