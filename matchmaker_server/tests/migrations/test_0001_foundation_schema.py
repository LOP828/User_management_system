import pytest
from django.db import connection


pytestmark = pytest.mark.django_db


def _table_columns(table_name):
    with connection.cursor() as cursor:
        return {column.name for column in connection.introspection.get_table_description(cursor, table_name)}


def _table_constraints(table_name):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table_name)


def test_foundation_tables_exist():
    tables = set(connection.introspection.table_names())
    assert "staff" in tables
    assert "reason_enum" in tables
    assert "payment_level" in tables
    assert "operation_log" in tables


def test_staff_key_columns_exist():
    columns = _table_columns("staff")
    assert {"id", "phone", "name", "role", "status", "password"}.issubset(columns)


def test_config_tables_key_columns_exist():
    assert {"id", "category", "label", "sort_order", "is_active"}.issubset(_table_columns("reason_enum"))
    assert {"id", "name", "homepage_weight", "recommend_limit", "pause_revisit_days"}.issubset(_table_columns("payment_level"))


def test_oplog_key_columns_exist():
    columns = _table_columns("operation_log")
    assert {"id", "operator_id", "action", "target_type", "target_id", "created_at"}.issubset(columns)


def test_oplog_foreign_key_exists():
    constraints = _table_constraints("operation_log")
    assert any(
        details.get("foreign_key") and details["columns"] == ["operator_id"]
        for details in constraints.values()
    )
