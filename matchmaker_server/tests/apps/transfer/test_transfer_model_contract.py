import pytest
from django.db import IntegrityError

from apps.transfer.models import UserTransferRequest


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

def test_status_constants():
    assert UserTransferRequest.STATUS_PENDING == "pending"
    assert UserTransferRequest.STATUS_APPROVED == "approved"
    assert UserTransferRequest.STATUS_REJECTED == "rejected"


# ---------------------------------------------------------------------------
# Default status is pending
# ---------------------------------------------------------------------------

def test_default_status_is_pending(create_customer_profile, create_staff):
    user = create_customer_profile()
    from_staff = create_staff(name="发起红娘")
    to_staff = create_staff(name="接收红娘")

    req = UserTransferRequest.objects.create(
        user=user,
        from_staff=from_staff,
        to_staff=to_staff,
        reason="工作调整",
    )
    assert req.status == UserTransferRequest.STATUS_PENDING


# ---------------------------------------------------------------------------
# Nullable optional fields
# ---------------------------------------------------------------------------

def test_optional_fields_nullable(create_customer_profile, create_staff):
    user = create_customer_profile()
    from_staff = create_staff(name="发起红娘2")
    to_staff = create_staff(name="接收红娘2")

    req = UserTransferRequest.objects.create(
        user=user,
        from_staff=from_staff,
        to_staff=to_staff,
        reason="调剂安排",
    )
    assert req.reviewer is None
    assert req.review_note is None
    assert req.reviewed_at is None


# ---------------------------------------------------------------------------
# Reviewer fields can be set
# ---------------------------------------------------------------------------

def test_reviewer_fields_can_be_set(create_customer_profile, create_staff):
    from django.utils import timezone

    user = create_customer_profile()
    from_staff = create_staff(name="发起红娘3")
    to_staff = create_staff(name="接收红娘3")
    reviewer = create_staff(name="审核管理员")
    now = timezone.now()

    req = UserTransferRequest.objects.create(
        user=user,
        from_staff=from_staff,
        to_staff=to_staff,
        reason="原因",
        status=UserTransferRequest.STATUS_APPROVED,
        reviewer=reviewer,
        review_note="同意转移",
        reviewed_at=now,
    )
    req.refresh_from_db()
    assert req.reviewer_id == reviewer.id
    assert req.review_note == "同意转移"
    assert req.reviewed_at is not None


# ---------------------------------------------------------------------------
# Check constraint: invalid status rejected at DB level
# ---------------------------------------------------------------------------

def test_invalid_status_violates_check_constraint(create_customer_profile, create_staff):
    user = create_customer_profile()
    from_staff = create_staff(name="发起红娘4")
    to_staff = create_staff(name="接收红娘4")

    with pytest.raises(IntegrityError):
        UserTransferRequest.objects.create(
            user=user,
            from_staff=from_staff,
            to_staff=to_staff,
            reason="测试",
            status="invalid_status",
        )


# ---------------------------------------------------------------------------
# created_at is auto-populated
# ---------------------------------------------------------------------------

def test_created_at_is_auto_populated(create_customer_profile, create_staff):
    user = create_customer_profile()
    from_staff = create_staff(name="发起红娘5")
    to_staff = create_staff(name="接收红娘5")

    req = UserTransferRequest.objects.create(
        user=user,
        from_staff=from_staff,
        to_staff=to_staff,
        reason="自动时间",
    )
    assert req.created_at is not None


# ---------------------------------------------------------------------------
# ForeignKey: user deletion blocked (PROTECT)
# ---------------------------------------------------------------------------

def test_user_fk_protect_on_delete(create_customer_profile, create_staff):
    from django.db.models import ProtectedError

    user = create_customer_profile()
    from_staff = create_staff(name="发起红娘6")
    to_staff = create_staff(name="接收红娘6")

    UserTransferRequest.objects.create(
        user=user,
        from_staff=from_staff,
        to_staff=to_staff,
        reason="保护测试",
    )

    with pytest.raises(ProtectedError):
        user.delete()


# ---------------------------------------------------------------------------
# db_table name
# ---------------------------------------------------------------------------

def test_db_table_name():
    assert UserTransferRequest._meta.db_table == "user_transfer_request"
