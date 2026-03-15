# Generated manually for the MVP scaffold.

from django.db import migrations


PAUSE_REASONS = [
    "忙工作",
    "忙考试",
    "情绪问题",
    "家庭因素",
    "对平台不满",
    "暂时不想见",
    "其他",
]

OVERDUE_REASONS = [
    "用户拖延",
    "对方拖延",
    "库存不足",
    "排期冲突",
    "资料未补全",
    "红娘未推进",
    "其他",
]

RISK_REASONS = [
    "一方降温",
    "异地",
    "家庭阻力",
    "节奏不一致",
    "失联",
    "现实条件冲突",
    "沟通冲突",
    "其他",
]


def seed_reason_enum(apps, schema_editor):
    ReasonEnum = apps.get_model("config_mgmt", "ReasonEnum")

    seed_map = {
        "pause": PAUSE_REASONS,
        "overdue": OVERDUE_REASONS,
        "risk": RISK_REASONS,
    }

    for category, labels in seed_map.items():
        for sort_order, label in enumerate(labels, start=1):
            ReasonEnum.objects.get_or_create(
                category=category,
                label=label,
                defaults={
                    "sort_order": sort_order,
                    "is_active": True,
                },
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("config_mgmt", "0002_payment_level"),
    ]

    operations = [
        migrations.RunPython(seed_reason_enum, noop_reverse),
    ]
