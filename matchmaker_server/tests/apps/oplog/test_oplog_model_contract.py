from apps.oplog.models import OperationLog


def test_operation_log_meta_contract():
    assert OperationLog._meta.db_table == "operation_log"
    assert OperationLog._meta.get_field("operator").target_field.name == "id"
    assert OperationLog._meta.get_field("before_json").null is True
    assert OperationLog._meta.get_field("before_json").blank is True
    assert OperationLog._meta.get_field("after_json").null is True
    assert OperationLog._meta.get_field("after_json").blank is True
    assert OperationLog._meta.get_field("reason").null is True
    assert OperationLog._meta.get_field("reason").blank is True


def test_operation_log_indexes_match_canonical_schema():
    indexes = {tuple(index.fields) for index in OperationLog._meta.indexes}
    assert ("target_type", "target_id", "created_at") in indexes
    assert ("operator", "created_at") in indexes
    assert ("created_at",) in indexes
