from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.user.models import CustomerProfile


pytestmark = pytest.mark.django_db

URL = "/api/v1/recommendations/candidate-search/"


def _candidate(create_customer_profile, owner, *, name="候选人", gender=CustomerProfile.GENDER_FEMALE, **kwargs):
    suffix = f"{uuid4().int % 10**8:08d}"
    defaults = {
        "owner": owner,
        "name": name,
        "gender": gender,
        "phone": f"139{suffix}",
        "wechat": f"wx_{suffix}",
        "city": "成都",
        "is_profile_complete": True,
        "pool_status": CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        "is_in_match": False,
    }
    defaults.update(kwargs)
    return create_customer_profile(**defaults)


@pytest.fixture
def target_user(create_customer_profile, create_payment_level, matchmaker_staff):
    payment_level = create_payment_level(recommend_limit=3)
    return create_customer_profile(
        owner=matchmaker_staff,
        payment_level=payment_level,
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
        gender=CustomerProfile.GENDER_MALE,
        city="成都",
    )


def test_candidate_search_hits_and_returns_expected_fields(
    auth_client,
    matchmaker_staff,
    target_user,
    create_customer_profile,
):
    candidate = _candidate(create_customer_profile, matchmaker_staff, name="李美丽")

    resp = auth_client(matchmaker_staff).get(
        f"{URL}?user_id={target_user.id}&search=美丽"
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert "page" in data
    assert "page_size" in data
    assert len(data["results"]) == 1

    item = data["results"][0]
    assert item["id"] == candidate.id
    assert item["name"] == "李美丽"
    assert item["gender"] == CustomerProfile.GENDER_FEMALE
    assert item["city"] == "成都"
    assert "payment_level_name" in item
    assert item["pool_status_display"] == "已沟通待推荐"
    assert item["is_profile_complete"] is True
    assert item["duplicate_warning"] is None


def test_candidate_search_returns_empty_when_no_result(
    auth_client,
    matchmaker_staff,
    target_user,
):
    resp = auth_client(matchmaker_staff).get(
        f"{URL}?user_id={target_user.id}&search=不存在的关键词"
    )

    assert resp.status_code == 200
    assert resp.json()["count"] == 0
    assert resp.json()["results"] == []


def test_candidate_search_pagination(
    auth_client,
    matchmaker_staff,
    target_user,
    create_customer_profile,
):
    for i in range(3):
        _candidate(create_customer_profile, matchmaker_staff, name=f"分页候选{i}")

    resp = auth_client(matchmaker_staff).get(
        f"{URL}?user_id={target_user.id}&page_size=2&page=2"
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert data["page"] == 2
    assert data["page_size"] == 2
    assert len(data["results"]) == 1


def test_candidate_search_permission_for_target_user(
    auth_client,
    create_staff,
    target_user,
):
    other_matchmaker = create_staff(name="其他红娘")

    resp = auth_client(other_matchmaker).get(f"{URL}?user_id={target_user.id}")

    assert resp.status_code == 403


def test_candidate_search_admin_allowed_for_any_target(
    auth_client,
    admin_staff,
    target_user,
):
    resp = auth_client(admin_staff).get(f"{URL}?user_id={target_user.id}")
    assert resp.status_code == 200


def test_candidate_search_filters_out_invalid_candidates(
    auth_client,
    matchmaker_staff,
    target_user,
    create_customer_profile,
    create_staff,
):
    valid = _candidate(create_customer_profile, matchmaker_staff, name="合法候选")
    _candidate(
        create_customer_profile,
        matchmaker_staff,
        name="暂停候选",
        pool_status=CustomerProfile.STATUS_PAUSED,
    )
    _candidate(
        create_customer_profile,
        matchmaker_staff,
        name="配对中候选",
        is_in_match=True,
    )
    _candidate(
        create_customer_profile,
        matchmaker_staff,
        name="同性候选",
        gender=CustomerProfile.GENDER_MALE,
    )
    deleted_candidate = _candidate(create_customer_profile, create_staff(name="软删红娘"), name="已删除候选")
    deleted_candidate.deleted_at = timezone.now()
    deleted_candidate.save(update_fields=["deleted_at"])

    resp = auth_client(matchmaker_staff).get(f"{URL}?user_id={target_user.id}")

    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["results"]}
    assert "合法候选" in names
    assert "暂停候选" not in names
    assert "配对中候选" not in names
    assert "同性候选" not in names
    assert "已删除候选" not in names
    assert valid.id in {item["id"] for item in resp.json()["results"]}


def test_candidate_search_duplicate_warning(
    auth_client,
    matchmaker_staff,
    target_user,
    create_customer_profile,
):
    candidate = _candidate(create_customer_profile, matchmaker_staff, name="重复候选")
    batch = RecommendationBatch.objects.create(
        user=target_user,
        staff=matchmaker_staff,
        batch_no="REC-CSEARCH-001",
        candidate_count=1,
        status=RecommendationBatch.STATUS_CLOSED,
        created_at=timezone.now() - timedelta(days=10),
    )
    RecommendationCandidate.objects.create(
        batch=batch,
        candidate_user=candidate,
        is_met=False,
    )

    resp = auth_client(matchmaker_staff).get(
        f"{URL}?user_id={target_user.id}&search=重复候选"
    )

    assert resp.status_code == 200
    item = resp.json()["results"][0]
    assert item["id"] == candidate.id
    assert item["duplicate_warning"] is not None
    assert item["duplicate_warning"]["level"] == "warning"
    assert item["duplicate_warning"]["message"] == "该候选人曾被推荐但未见面"


def test_candidate_search_duplicate_warning_danger_for_not_continue(
    auth_client,
    matchmaker_staff,
    target_user,
    create_customer_profile,
):
    candidate = _candidate(create_customer_profile, matchmaker_staff, name="未继续候选")
    batch = RecommendationBatch.objects.create(
        user=target_user,
        staff=matchmaker_staff,
        batch_no="REC-CSEARCH-002",
        candidate_count=1,
        status=RecommendationBatch.STATUS_CLOSED,
    )
    RecommendationCandidate.objects.create(
        batch=batch,
        candidate_user=candidate,
        is_met=True,
        result=RecommendationCandidate.RESULT_NOT_CONTINUE,
    )

    resp = auth_client(matchmaker_staff).get(
        f"{URL}?user_id={target_user.id}&search=未继续候选"
    )

    assert resp.status_code == 200
    item = resp.json()["results"][0]
    assert item["duplicate_warning"]["level"] == "danger"
    assert item["duplicate_warning"]["message"] == "该候选人曾见面但未继续"
