import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from uuid import uuid4

from apps.config_mgmt.models import PaymentLevel, ReasonEnum
from apps.staff.models import Staff
from apps.user.models import CustomerProfile


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def create_staff(db):
    def factory(**kwargs):
        password = kwargs.pop("password", "Passw0rd123!")
        defaults = {
            "name": "测试红娘",
            "phone": f"138{uuid4().int % 10**8:08d}",
            "role": Staff.ROLE_MATCHMAKER,
            "status": Staff.STATUS_ACTIVE,
            "wechat_id": "wx_test",
        }
        defaults.update(kwargs)
        return Staff.objects.create_user(password=password, **defaults)

    return factory


@pytest.fixture
def admin_staff(create_staff):
    return create_staff(
        name="管理员",
        role=Staff.ROLE_ADMIN,
        wechat_id="wx_admin",
    )


@pytest.fixture
def matchmaker_staff(create_staff):
    return create_staff()


@pytest.fixture
def auth_client(api_client):
    def factory(staff):
        refresh = RefreshToken.for_user(staff)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    return factory


@pytest.fixture
def create_reason_enum(db):
    def factory(**kwargs):
        defaults = {
            "category": ReasonEnum.CATEGORY_PAUSE,
            "label": "忙工作",
            "sort_order": 1,
            "is_active": True,
        }
        defaults.update(kwargs)
        return ReasonEnum.objects.create(**defaults)

    return factory


@pytest.fixture
def create_payment_level(db):
    def factory(**kwargs):
        defaults = {
            "name": "标准会员",
            "sort_order": 1,
            "is_active": True,
            "homepage_weight": 10,
            "recommend_limit": 3,
            "pause_revisit_days": 30,
            "followup_timeout_days": 7,
            "note": "",
        }
        defaults.update(kwargs)
        return PaymentLevel.objects.create(**defaults)

    return factory


@pytest.fixture
def create_customer_profile(db, matchmaker_staff, create_payment_level):
    def factory(**kwargs):
        payment_level = kwargs.pop("payment_level", None) or create_payment_level()
        owner = kwargs.pop("owner", None) or matchmaker_staff
        explicit_last_unmatched_active_at = "last_unmatched_active_at" in kwargs
        defaults = {
            "name": "张三",
            "gender": CustomerProfile.GENDER_MALE,
            "age": 28,
            "phone": "13900139000",
            "wechat": "zhangsan_wx",
            "other_contact": "",
            "city": "成都",
            "payment_level": payment_level,
            "owner": owner,
            "basic_requirement": "希望找25-30岁，成都本地",
            "pool_status": CustomerProfile.STATUS_NEW_PENDING,
            "is_profile_complete": False,
            "is_in_match": False,
            "tags": [],
        }
        defaults.update(kwargs)
        user = CustomerProfile.objects.create(**defaults)
        if not explicit_last_unmatched_active_at and user.last_unmatched_active_at is None:
            user.last_unmatched_active_at = user.created_at
            user.save(update_fields=["last_unmatched_active_at", "updated_at"])
        return user

    return factory
