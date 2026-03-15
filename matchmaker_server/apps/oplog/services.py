from apps.oplog.models import OperationLog


def create_operation_log(
    *,
    operator,
    action,
    target_type,
    target_id,
    before_json=None,
    after_json=None,
    reason=None,
):
    return OperationLog.objects.create(
        operator=operator,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before_json=before_json,
        after_json=after_json,
        reason=reason,
    )
