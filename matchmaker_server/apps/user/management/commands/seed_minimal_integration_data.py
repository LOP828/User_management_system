import os
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.config_mgmt.models import PaymentLevel
from apps.staff.models import Staff
from apps.user.models import CustomerProfile
from apps.user.services import annotate_priority_score, create_customer_profile


DEFAULT_ADMIN_PHONE = "13800000000"
DEFAULT_ADMIN_NAME = "默认管理员"
DEFAULT_ADMIN_PASSWORD = "Passw0rd123!"
DEFAULT_OWNER_PHONE = "13800000001"
DEFAULT_OWNER_PASSWORD = "Passw0rd123!"

PAYMENT_LEVEL_SPECS = (
    {
        "name": "联调基础档",
        "sort_order": 101,
        "homepage_weight": 5,
        "recommend_limit": 3,
        "pause_revisit_days": 30,
        "followup_timeout_days": 7,
        "note": "前端最小联调数据",
    },
    {
        "name": "联调中级档",
        "sort_order": 102,
        "homepage_weight": 30,
        "recommend_limit": 3,
        "pause_revisit_days": 30,
        "followup_timeout_days": 7,
        "note": "前端最小联调数据",
    },
    {
        "name": "联调超时档",
        "sort_order": 103,
        "homepage_weight": 10,
        "recommend_limit": 3,
        "pause_revisit_days": 30,
        "followup_timeout_days": 7,
        "note": "前端最小联调数据",
    },
)

USER_SPECS = (
    {
        "phone": "13990000001",
        "wechat": "seed_min_user_low",
        "name": "联调低分用户",
        "gender": CustomerProfile.GENDER_MALE,
        "age": 28,
        "city": "上海",
        "basic_requirement": "希望找上海本地，沟通稳定。",
        "payment_level_name": "联调基础档",
        "paid_at_days_ago": None,
        "expected_score": 5,
    },
    {
        "phone": "13990000002",
        "wechat": "seed_min_user_mid",
        "name": "联调中分用户",
        "gender": CustomerProfile.GENDER_FEMALE,
        "age": 26,
        "city": "杭州",
        "basic_requirement": "希望找杭州本地，年龄相近。",
        "payment_level_name": "联调中级档",
        "paid_at_days_ago": None,
        "expected_score": 30,
    },
    {
        "phone": "13990000003",
        "wechat": "seed_min_user_high",
        "name": "联调高分用户",
        "gender": CustomerProfile.GENDER_MALE,
        "age": 31,
        "city": "成都",
        "basic_requirement": "希望找成都本地，可接受短期异地。",
        "payment_level_name": "联调超时档",
        "paid_at_days_ago": 10,
        "expected_score": 40,
    },
)


class Command(BaseCommand):
    help = "Seed the smallest reusable integration dataset for /api/v1/users/."

    @transaction.atomic
    def handle(self, *args, **options):
        admin = self._ensure_admin()
        owner = self._ensure_owner()
        payment_levels = self._ensure_payment_levels()
        users = self._ensure_users(actor=owner, owner=owner, payment_levels=payment_levels)

        scored_users = list(
            annotate_priority_score(
                CustomerProfile.objects.filter(id__in=[user.id for user in users]).select_related("payment_level")
            ).order_by("-priority_score", "id")
        )

        self.stdout.write(self.style.SUCCESS("Minimal integration data is ready."))
        self.stdout.write(f"login_admin_phone={admin.phone}")
        self.stdout.write(f"login_admin_password={self._admin_password()}")
        self.stdout.write(f"owner_phone={owner.phone}")
        self.stdout.write(f"owner_password={DEFAULT_OWNER_PASSWORD}")
        for user in scored_users:
            self.stdout.write(
                f"user id={user.id} name={user.name} payment_level={user.payment_level.name} "
                f"priority_score={user.priority_score}"
            )

    def _ensure_admin(self):
        os.environ.setdefault("INIT_ADMIN_PHONE", DEFAULT_ADMIN_PHONE)
        os.environ.setdefault("INIT_ADMIN_NAME", DEFAULT_ADMIN_NAME)
        os.environ.setdefault("INIT_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
        os.environ.setdefault("INIT_ADMIN_WECHAT_ID", "")
        call_command("init_admin")
        return Staff.objects.get(phone=os.environ["INIT_ADMIN_PHONE"])

    def _admin_password(self):
        return os.environ.get("INIT_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)

    def _ensure_owner(self):
        owner, _ = Staff.objects.get_or_create(
            phone=DEFAULT_OWNER_PHONE,
            defaults={
                "name": "联调红娘",
                "role": Staff.ROLE_MATCHMAKER,
                "status": Staff.STATUS_ACTIVE,
                "wechat_id": "seed_matchmaker",
            },
        )
        changed = []
        for field, value in (
            ("name", "联调红娘"),
            ("role", Staff.ROLE_MATCHMAKER),
            ("status", Staff.STATUS_ACTIVE),
            ("wechat_id", "seed_matchmaker"),
        ):
            if getattr(owner, field) != value:
                setattr(owner, field, value)
                changed.append(field)
        owner.set_password(DEFAULT_OWNER_PASSWORD)
        changed.append("password")
        owner.save(update_fields=[*changed, "updated_at"])
        return owner

    def _ensure_payment_levels(self):
        payment_levels = {}
        for spec in PAYMENT_LEVEL_SPECS:
            payment_level, _ = PaymentLevel.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "sort_order": spec["sort_order"],
                    "is_active": True,
                    "homepage_weight": spec["homepage_weight"],
                    "recommend_limit": spec["recommend_limit"],
                    "pause_revisit_days": spec["pause_revisit_days"],
                    "followup_timeout_days": spec["followup_timeout_days"],
                    "note": spec["note"],
                },
            )
            changed = []
            for field in (
                "sort_order",
                "homepage_weight",
                "recommend_limit",
                "pause_revisit_days",
                "followup_timeout_days",
                "note",
            ):
                if getattr(payment_level, field) != spec[field]:
                    setattr(payment_level, field, spec[field])
                    changed.append(field)
            if payment_level.is_active is not True:
                payment_level.is_active = True
                changed.append("is_active")
            if changed:
                payment_level.save(update_fields=[*changed, "updated_at"])
            payment_levels[payment_level.name] = payment_level
        return payment_levels

    def _ensure_users(self, *, actor, owner, payment_levels):
        old_date = timezone.now() - timedelta(days=30)
        users = []
        for spec in USER_SPECS:
            defaults = {
                "name": spec["name"],
                "gender": spec["gender"],
                "age": spec["age"],
                "phone": spec["phone"],
                "wechat": spec["wechat"],
                "other_contact": "",
                "city": spec["city"],
                "payment_level": payment_levels[spec["payment_level_name"]],
                "owner": owner,
                "basic_requirement": spec["basic_requirement"],
                "profile_detail": {},
                "tags": [],
            }
            user = CustomerProfile.objects.filter(phone=spec["phone"], deleted_at__isnull=True).first()
            if user is None:
                user = create_customer_profile(defaults, actor)
            changed = []
            for field, value in (
                ("name", spec["name"]),
                ("gender", spec["gender"]),
                ("age", spec["age"]),
                ("phone", spec["phone"]),
                ("wechat", spec["wechat"]),
                ("other_contact", ""),
                ("city", spec["city"]),
                ("payment_level", payment_levels[spec["payment_level_name"]]),
                ("owner", owner),
                ("basic_requirement", spec["basic_requirement"]),
                ("pool_status", CustomerProfile.STATUS_NEW_PENDING),
                ("pre_pause_status", None),
                ("is_profile_complete", False),
                ("is_in_match", False),
                ("profile_detail", {}),
                ("emotional_history", None),
                ("tags", []),
                ("deleted_at", None),
            ):
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed.append(field)
            paid_at = None
            if spec["paid_at_days_ago"] is not None:
                paid_at = timezone.now() - timedelta(days=spec["paid_at_days_ago"])
            if user.paid_at != paid_at:
                user.paid_at = paid_at
                changed.append("paid_at")
            if user.created_at != old_date:
                user.created_at = old_date
                changed.append("created_at")
            if user.last_unmatched_active_at != old_date:
                user.last_unmatched_active_at = old_date
                changed.append("last_unmatched_active_at")
            if changed:
                user.save(update_fields=[*changed, "updated_at"])
            users.append(user)
        return users
