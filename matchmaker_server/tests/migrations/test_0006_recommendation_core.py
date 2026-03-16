import pytest
from django.db import connection


pytestmark = pytest.mark.django_db


def _table_columns(table_name):
    with connection.cursor() as cursor:
        return {column.name for column in connection.introspection.get_table_description(cursor, table_name)}


def _table_constraints(table_name):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table_name)


def test_recommendation_batch_table_exists():
    assert "recommendation_batch" in set(connection.introspection.table_names())


def test_recommendation_candidate_table_exists():
    assert "recommendation_candidate" in set(connection.introspection.table_names())


def test_recommendation_batch_columns_exist():
    columns = _table_columns("recommendation_batch")
    assert {
        "id",
        "user_id",
        "staff_id",
        "batch_no",
        "candidate_count",
        "status",
        "created_at",
        "closed_at",
    }.issubset(columns)


def test_recommendation_candidate_columns_exist():
    columns = _table_columns("recommendation_candidate")
    assert {
        "id",
        "batch_id",
        "candidate_user_id",
        "is_selected",
        "is_met",
        "result",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_recommendation_batch_indexes_exist():
    constraints = _table_constraints("recommendation_batch")
    assert any(
        details.get("index") and set(details["columns"]) == {"user_id", "created_at"}
        for details in constraints.values()
    )
    assert any(
        details.get("index") and details["columns"] == ["staff_id"]
        for details in constraints.values()
    )


def test_recommendation_candidate_indexes_exist():
    constraints = _table_constraints("recommendation_candidate")
    assert any(
        details.get("index") and details["columns"] == ["batch_id"]
        for details in constraints.values()
    )
    assert any(
        details.get("index") and details["columns"] == ["candidate_user_id"]
        for details in constraints.values()
    )


def test_recommendation_batch_check_constraint_exists():
    constraints = _table_constraints("recommendation_batch")
    assert any(details.get("check") for details in constraints.values())


def test_recommendation_candidate_check_constraint_exists():
    constraints = _table_constraints("recommendation_candidate")
    assert any(details.get("check") for details in constraints.values())
