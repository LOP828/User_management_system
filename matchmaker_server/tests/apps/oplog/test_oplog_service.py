import pytest

from apps.oplog.models import OperationLog
from apps.oplog.services import create_operation_log


pytestmark = pytest.mark.django_db


def test_create_operation_log_persists_structured_snapshot(create_staff):
    operator = create_staff(name="日志操作人")

    log = create_operation_log(
        operator=operator,
        action="user_status_changed",
        target_type="user",
        target_id=123,
        before_json={"pool_status": "new_pending"},
        after_json={"pool_status": "communicated_pending_recommend"},
        reason="首次沟通完成",
    )

    saved = OperationLog.objects.get(id=log.id)
    assert saved.operator_id == operator.id
    assert saved.action == "user_status_changed"
    assert saved.target_type == "user"
    assert saved.target_id == 123
    assert saved.before_json == {"pool_status": "new_pending"}
    assert saved.after_json == {"pool_status": "communicated_pending_recommend"}
    assert saved.reason == "首次沟通完成"
