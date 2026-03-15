import pytest
from django.core.management import call_command

from apps.staff.models import Staff


@pytest.mark.django_db
def test_init_admin_command_creates_and_updates_admin(monkeypatch):
    monkeypatch.setenv("INIT_ADMIN_PHONE", "13900139999")
    monkeypatch.setenv("INIT_ADMIN_NAME", "初始化管理员")
    monkeypatch.setenv("INIT_ADMIN_PASSWORD", "Passw0rd123!")
    monkeypatch.setenv("INIT_ADMIN_WECHAT_ID", "wx_init_admin")

    call_command("init_admin")

    staff = Staff.objects.get(phone="13900139999")
    assert staff.role == Staff.ROLE_ADMIN
    assert staff.status == Staff.STATUS_ACTIVE
    assert staff.check_password("Passw0rd123!")

    monkeypatch.setenv("INIT_ADMIN_NAME", "已更新管理员")
    monkeypatch.setenv("INIT_ADMIN_PASSWORD", "Passw0rd456!")
    call_command("init_admin")

    assert Staff.objects.filter(phone="13900139999").count() == 1
    staff.refresh_from_db()
    assert staff.name == "已更新管理员"
    assert staff.check_password("Passw0rd456!")
