import pytest
from django.db import connection


pytestmark = pytest.mark.django_db


def _table_columns(table_name):
    with connection.cursor() as cursor:
        return {column.name for column in connection.introspection.get_table_description(cursor, table_name)}


def _table_constraints(table_name):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table_name)


def test_reminder_table_exists():
    assert "reminder" in set(connection.introspection.table_names())


def test_reminder_columns_exist():
    columns = _table_columns("reminder")
    assert {
        "target_type",
        "target_id",
        "staff_id",
        "remind_type",
        "remind_at",
        "status",
        "processed_at",
        "is_manual",
        "created_at",
    }.issubset(columns)


def test_reminder_foreign_key_and_indexes_exist():
    constraints = _table_constraints("reminder")
    assert any(
        details.get("foreign_key") and details["columns"] == ["staff_id"]
        for details in constraints.values()
    )
    assert any(
        details.get("index") and details["columns"] == ["staff_id", "status", "remind_at"]
        for details in constraints.values()
    )
    assert any(
        details.get("index") and details["columns"] == ["target_type", "target_id"]
        for details in constraints.values()
    )
    assert any(
        details.get("index") and details["columns"] == ["remind_at", "status"]
        for details in constraints.values()
    )


def test_reminder_check_constraints_exist():
    constraints = _table_constraints("reminder")
    assert sum(1 for details in constraints.values() if details.get("check")) >= 3
