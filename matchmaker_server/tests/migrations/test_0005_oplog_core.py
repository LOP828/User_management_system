import pytest
from django.db import connection


pytestmark = pytest.mark.django_db


def _table_columns(table_name):
    with connection.cursor() as cursor:
        return {column.name for column in connection.introspection.get_table_description(cursor, table_name)}


def _table_constraints(table_name):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table_name)


def test_operation_log_table_has_canonical_columns():
    columns = _table_columns("operation_log")
    assert {
        "operator_id",
        "action",
        "target_type",
        "target_id",
        "before_json",
        "after_json",
        "reason",
        "created_at",
    }.issubset(columns)
    assert "field_changed" not in columns
    assert "old_value" not in columns
    assert "new_value" not in columns


def test_operation_log_indexes_exist():
    constraints = _table_constraints("operation_log")
    assert any(
        details.get("index") and details["columns"] == ["target_type", "target_id", "created_at"]
        for details in constraints.values()
    )
    assert any(
        details.get("index") and details["columns"] == ["operator_id", "created_at"]
        for details in constraints.values()
    )
    assert any(
        details.get("index") and details["columns"] == ["created_at"]
        for details in constraints.values()
    )
