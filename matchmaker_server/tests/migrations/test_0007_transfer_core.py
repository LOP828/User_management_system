import pytest
from django.db import connection


pytestmark = pytest.mark.django_db


def _table_columns(table_name):
    with connection.cursor() as cursor:
        return {column.name for column in connection.introspection.get_table_description(cursor, table_name)}


def _table_constraints(table_name):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table_name)


def test_user_transfer_request_table_exists():
    assert "user_transfer_request" in set(connection.introspection.table_names())


def test_user_transfer_request_columns_exist():
    columns = _table_columns("user_transfer_request")
    assert {
        "id",
        "user_id",
        "from_staff_id",
        "to_staff_id",
        "reason",
        "status",
        "reviewer_id",
        "review_note",
        "reviewed_at",
        "created_at",
    }.issubset(columns)


def test_user_transfer_request_user_index_exists():
    constraints = _table_constraints("user_transfer_request")
    assert any(
        details.get("index") and details["columns"] == ["user_id"]
        for details in constraints.values()
    )


def test_user_transfer_request_status_index_exists():
    constraints = _table_constraints("user_transfer_request")
    assert any(
        details.get("index") and details["columns"] == ["status"]
        for details in constraints.values()
    )


def test_user_transfer_request_from_staff_index_exists():
    constraints = _table_constraints("user_transfer_request")
    assert any(
        details.get("index") and details["columns"] == ["from_staff_id"]
        for details in constraints.values()
    )


def test_user_transfer_request_check_constraint_exists():
    constraints = _table_constraints("user_transfer_request")
    assert any(details.get("check") for details in constraints.values())
