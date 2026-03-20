import pytest
from django.db import IntegrityError, transaction

from apps.recommendation.models import RecommendationBatch, RecommendationCandidate


pytestmark = pytest.mark.django_db


def test_recommendation_batch_meta_contract():
    assert RecommendationBatch._meta.db_table == "recommendation_batch"
    assert RecommendationBatch._meta.get_field("status").default == RecommendationBatch.STATUS_OPEN
    assert RecommendationBatch._meta.get_field("candidate_count").default == 0
    assert RecommendationBatch._meta.get_field("closed_at").null is True
    assert RecommendationBatch._meta.get_field("closed_at").blank is True


def test_recommendation_candidate_meta_contract():
    assert RecommendationCandidate._meta.db_table == "recommendation_candidate"
    assert RecommendationCandidate._meta.get_field("is_selected").default is False
    assert RecommendationCandidate._meta.get_field("is_met").default is False
    assert RecommendationCandidate._meta.get_field("result").null is True
    assert RecommendationCandidate._meta.get_field("result").blank is True


def test_recommendation_candidate_enforces_single_selected_per_batch(create_staff, create_customer_profile):
    user = create_customer_profile()
    first_candidate_user = create_customer_profile(name="候选人丙", gender="female")
    second_candidate_user = create_customer_profile(name="候选人丁", gender="female")
    staff = create_staff()
    batch = RecommendationBatch.objects.create(user=user, staff=staff, batch_no="REC-20260316-005")

    RecommendationCandidate.objects.create(
        batch=batch,
        candidate_user=first_candidate_user,
        is_selected=True,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RecommendationCandidate.objects.create(
                batch=batch,
                candidate_user=second_candidate_user,
                is_selected=True,
            )


def test_recommendation_batch_allows_minimal_fields(create_staff, create_customer_profile):
    user = create_customer_profile()
    staff = create_staff()
    batch = RecommendationBatch.objects.create(
        user=user,
        staff=staff,
        batch_no="REC-20260316-001",
    )
    assert batch.status == RecommendationBatch.STATUS_OPEN
    assert batch.candidate_count == 0
    assert batch.closed_at is None


def test_recommendation_batch_batch_no_is_unique(create_staff, create_customer_profile):
    user = create_customer_profile()
    staff = create_staff()
    RecommendationBatch.objects.create(user=user, staff=staff, batch_no="REC-20260316-001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RecommendationBatch.objects.create(user=user, staff=staff, batch_no="REC-20260316-001")


def test_recommendation_batch_rejects_invalid_status(create_staff, create_customer_profile):
    user = create_customer_profile()
    staff = create_staff()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RecommendationBatch.objects.create(
                user=user,
                staff=staff,
                batch_no="REC-20260316-002",
                status="invalid_status",
            )


def test_recommendation_candidate_allows_null_result(create_staff, create_customer_profile):
    user = create_customer_profile()
    candidate_user = create_customer_profile(name="候选人甲", gender="female")
    staff = create_staff()
    batch = RecommendationBatch.objects.create(user=user, staff=staff, batch_no="REC-20260316-003")
    candidate = RecommendationCandidate.objects.create(batch=batch, candidate_user=candidate_user)
    assert candidate.result is None
    assert candidate.is_selected is False
    assert candidate.is_met is False


def test_recommendation_candidate_rejects_invalid_result(create_staff, create_customer_profile):
    user = create_customer_profile()
    candidate_user = create_customer_profile(name="候选人乙", gender="female")
    staff = create_staff()
    batch = RecommendationBatch.objects.create(user=user, staff=staff, batch_no="REC-20260316-004")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RecommendationCandidate.objects.create(
                batch=batch,
                candidate_user=candidate_user,
                result="invalid_result",
            )
