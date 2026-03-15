import pytest

from apps.config_mgmt.models import ReasonEnum
from apps.staff.models import Staff


pytestmark = pytest.mark.django_db


def test_reason_enum_seeded_defaults_exist():
    assert ReasonEnum.objects.filter(category="pause").count() == 7
    assert ReasonEnum.objects.filter(category="overdue").count() == 7
    assert ReasonEnum.objects.filter(category="risk").count() == 8


def test_reason_enum_seed_does_not_insert_placeholder_categories():
    assert ReasonEnum.objects.filter(category="meet_failure").count() == 0
    assert ReasonEnum.objects.filter(category="transfer").count() == 0
    assert ReasonEnum.objects.filter(category="success_invalidate").count() == 0
    assert ReasonEnum.objects.filter(category="match_end").count() == 0


def test_seed_does_not_create_default_admin():
    assert Staff.objects.count() == 0
