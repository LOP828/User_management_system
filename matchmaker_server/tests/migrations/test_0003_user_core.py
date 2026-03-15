import pytest
from django.db import connection


pytestmark = pytest.mark.django_db


def _table_columns(table_name):
    with connection.cursor() as cursor:
        return {column.name for column in connection.introspection.get_table_description(cursor, table_name)}


def _table_constraints(table_name):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table_name)


def test_user_core_tables_exist():
    tables = set(connection.introspection.table_names())
    assert "user" in tables
    assert "user_status_history" in tables


def test_user_core_columns_exist():
    user_columns = _table_columns("user")
    assert {
        "pool_status",
        "is_in_match",
        "paid_at",
        "last_action_at",
        "last_unmatched_active_at",
        "owner_id",
        "payment_level_id",
    }.issubset(user_columns)

    history_columns = _table_columns("user_status_history")
    assert {"user_id", "changed_by_id", "reason_id", "reason_note", "to_status"}.issubset(history_columns)


def test_user_core_foreign_keys_exist():
    user_constraints = _table_constraints("user")
    assert any(
        details.get("foreign_key") and details["columns"] == ["owner_id"]
        for details in user_constraints.values()
    )
    assert any(
        details.get("foreign_key") and details["columns"] == ["payment_level_id"]
        for details in user_constraints.values()
    )

    history_constraints = _table_constraints("user_status_history")
    assert any(
        details.get("foreign_key") and details["columns"] == ["user_id"]
        for details in history_constraints.values()
    )
    assert any(
        details.get("foreign_key") and details["columns"] == ["changed_by_id"]
        for details in history_constraints.values()
    )
    assert any(
        details.get("foreign_key") and details["columns"] == ["reason_id"]
        for details in history_constraints.values()
    )


def test_user_core_static_constraints_exist():
    constraints = _table_constraints("user")
    assert any(details.get("check") for details in constraints.values())
