import pytest
from django.utils import timezone

from apps.recommendation.models import RecommendationBatch, RecommendationCandidate
from apps.user.models import CustomerProfile, UserStatusHistory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ready_user(create_customer_profile, create_payment_level):
    """A user in communicated_pending_recommend state with a complete profile."""
    payment_level = create_payment_level(recommend_limit=3)
    return create_customer_profile(
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
        payment_level=payment_level,
    )


@pytest.fixture
def candidate_user(create_customer_profile, create_staff):
    staff = create_staff(name="候选人红娘")
    return create_customer_profile(
        name="候选人甲",
        gender=CustomerProfile.GENDER_FEMALE,
        owner=staff,
    )


@pytest.fixture
def another_candidate_user(create_customer_profile, create_staff):
    staff = create_staff(name="候选人红娘2")
    return create_customer_profile(
        name="候选人乙",
        gender=CustomerProfile.GENDER_FEMALE,
        owner=staff,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/recommendations/ — create batch
# ---------------------------------------------------------------------------

def test_create_batch_success(auth_client, matchmaker_staff, ready_user, candidate_user):
    client = auth_client(matchmaker_staff)
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["owner", "updated_at"])

    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": ready_user.id, "candidate_user_ids": [candidate_user.id]},
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == RecommendationBatch.STATUS_OPEN
    assert data["candidate_count"] == 1
    assert len(data["candidates"]) == 1
    assert data["batch_no"].startswith("REC-")


def test_create_batch_updates_user_status(auth_client, matchmaker_staff, ready_user, candidate_user):
    client = auth_client(matchmaker_staff)
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["owner", "updated_at"])

    client.post(
        "/api/v1/recommendations/",
        data={"user_id": ready_user.id, "candidate_user_ids": [candidate_user.id]},
        format="json",
    )
    ready_user.refresh_from_db()
    assert ready_user.pool_status == CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT


def test_create_batch_updates_last_action_at_and_last_unmatched_active_at(
    auth_client, matchmaker_staff, ready_user, candidate_user
):
    client = auth_client(matchmaker_staff)
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["owner", "updated_at"])

    old_last_action = ready_user.last_action_at
    old_last_unmatched = ready_user.last_unmatched_active_at

    client.post(
        "/api/v1/recommendations/",
        data={"user_id": ready_user.id, "candidate_user_ids": [candidate_user.id]},
        format="json",
    )
    ready_user.refresh_from_db()
    assert ready_user.last_action_at is not None
    assert ready_user.last_action_at != old_last_action or old_last_action is None
    assert ready_user.last_unmatched_active_at is not None
    assert ready_user.last_unmatched_active_at != old_last_unmatched or old_last_unmatched is None


def test_create_batch_br_rec_001_wrong_status(auth_client, matchmaker_staff, create_customer_profile, candidate_user):
    client = auth_client(matchmaker_staff)
    user = create_customer_profile(
        pool_status=CustomerProfile.STATUS_NEW_PENDING,
        is_profile_complete=True,
        owner=matchmaker_staff,
    )
    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": user.id, "candidate_user_ids": [candidate_user.id]},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "BR_REC_001_STATUS"


def test_create_batch_br_rec_001_profile_incomplete(auth_client, matchmaker_staff, create_customer_profile, candidate_user):
    client = auth_client(matchmaker_staff)
    user = create_customer_profile(
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=False,
        owner=matchmaker_staff,
    )
    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": user.id, "candidate_user_ids": [candidate_user.id]},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "BR_REC_001_PROFILE"


def test_create_batch_br_rec_002_exceeds_limit(
    auth_client, matchmaker_staff, create_customer_profile, create_payment_level, candidate_user, another_candidate_user
):
    client = auth_client(matchmaker_staff)
    payment_level = create_payment_level(recommend_limit=1)
    user = create_customer_profile(
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
        payment_level=payment_level,
        owner=matchmaker_staff,
    )
    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": user.id, "candidate_user_ids": [candidate_user.id, another_candidate_user.id]},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "BR_REC_002"


def test_create_batch_br_rec_003_duplicate_warning(
    auth_client, matchmaker_staff, ready_user, candidate_user
):
    """Duplicate candidate should return a warning, not block creation."""
    client = auth_client(matchmaker_staff)
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["owner", "updated_at"])

    # Create first batch with this candidate
    batch = RecommendationBatch.objects.create(
        user=ready_user,
        staff=matchmaker_staff,
        batch_no="REC-20260101-001",
        candidate_count=1,
        status=RecommendationBatch.STATUS_CLOSED,
    )
    RecommendationCandidate.objects.create(batch=batch, candidate_user=candidate_user)

    # Reset user to valid state for second batch
    ready_user.pool_status = CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    ready_user.save(update_fields=["pool_status", "updated_at"])

    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": ready_user.id, "candidate_user_ids": [candidate_user.id]},
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "warnings" in data
    assert any(w["code"] == "BR_REC_003_DUPLICATE" for w in data["warnings"])
    assert candidate_user.id in data["warnings"][0]["duplicate_candidate_user_ids"]


def test_create_batch_matchmaker_cannot_create_for_other_staff_user(
    auth_client, create_staff, create_customer_profile, create_payment_level, candidate_user
):
    matchmaker = create_staff(name="红娘A")
    other_staff = create_staff(name="红娘B")
    payment_level = create_payment_level(recommend_limit=3)
    user = create_customer_profile(
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
        payment_level=payment_level,
        owner=other_staff,
    )
    client = auth_client(matchmaker)
    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": user.id, "candidate_user_ids": [candidate_user.id]},
        format="json",
    )
    assert resp.status_code == 403


def test_admin_can_create_batch_for_any_user(
    auth_client, admin_staff, create_staff, create_customer_profile, create_payment_level, candidate_user
):
    other_staff = create_staff(name="他人红娘")
    payment_level = create_payment_level(recommend_limit=3)
    user = create_customer_profile(
        pool_status=CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND,
        is_profile_complete=True,
        payment_level=payment_level,
        owner=other_staff,
    )
    client = auth_client(admin_staff)
    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": user.id, "candidate_user_ids": [candidate_user.id]},
        format="json",
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# POST /api/v1/recommendations/candidates/{id}/select/
# ---------------------------------------------------------------------------

def _create_open_batch(user, staff, candidate_user):
    batch = RecommendationBatch.objects.create(
        user=user,
        staff=staff,
        batch_no="REC-20260316-TEST",
        candidate_count=1,
        status=RecommendationBatch.STATUS_OPEN,
    )
    candidate = RecommendationCandidate.objects.create(batch=batch, candidate_user=candidate_user)
    return batch, candidate


def test_select_candidate_success(auth_client, matchmaker_staff, ready_user, candidate_user):
    ready_user.pool_status = CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["pool_status", "owner", "updated_at"])
    batch, candidate = _create_open_batch(ready_user, matchmaker_staff, candidate_user)

    client = auth_client(matchmaker_staff)
    resp = client.post(f"/api/v1/recommendations/candidates/{candidate.id}/select/")
    assert resp.status_code == 200
    assert resp.json()["is_selected"] is True

    candidate.refresh_from_db()
    assert candidate.is_selected is True


def test_select_candidate_advances_user_status_to_selected_pending_meet(
    auth_client, matchmaker_staff, ready_user, candidate_user
):
    """S3→S4: selecting a candidate must advance user pool_status."""
    ready_user.pool_status = CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["pool_status", "owner", "updated_at"])
    batch, candidate = _create_open_batch(ready_user, matchmaker_staff, candidate_user)

    client = auth_client(matchmaker_staff)
    old_last_action = ready_user.last_action_at
    old_last_unmatched = ready_user.last_unmatched_active_at
    client.post(f"/api/v1/recommendations/candidates/{candidate.id}/select/")

    ready_user.refresh_from_db()
    assert ready_user.pool_status == CustomerProfile.STATUS_SELECTED_PENDING_MEET
    assert ready_user.last_action_at is not None
    assert ready_user.last_unmatched_active_at is not None
    if old_last_action is not None:
        assert ready_user.last_action_at > old_last_action
    if old_last_unmatched is not None:
        assert ready_user.last_unmatched_active_at > old_last_unmatched
    history = UserStatusHistory.objects.filter(user=ready_user).order_by("-created_at").first()
    assert history.to_status == CustomerProfile.STATUS_SELECTED_PENDING_MEET


def test_select_candidate_blocks_second_selection_in_same_batch(
    auth_client,
    matchmaker_staff,
    ready_user,
    candidate_user,
    another_candidate_user,
):
    ready_user.pool_status = CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["pool_status", "owner", "updated_at"])
    batch = RecommendationBatch.objects.create(
        user=ready_user,
        staff=matchmaker_staff,
        batch_no="REC-20260316-SEL-2",
        candidate_count=2,
        status=RecommendationBatch.STATUS_OPEN,
    )
    first_candidate = RecommendationCandidate.objects.create(batch=batch, candidate_user=candidate_user)
    second_candidate = RecommendationCandidate.objects.create(batch=batch, candidate_user=another_candidate_user)

    client = auth_client(matchmaker_staff)
    first_resp = client.post(f"/api/v1/recommendations/candidates/{first_candidate.id}/select/")
    assert first_resp.status_code == 200

    second_resp = client.post(f"/api/v1/recommendations/candidates/{second_candidate.id}/select/")
    assert second_resp.status_code == 400
    assert second_resp.json()["code"] == "BATCH_ALREADY_HAS_SELECTED_CANDIDATE"

    first_candidate.refresh_from_db()
    second_candidate.refresh_from_db()
    assert first_candidate.is_selected is True
    assert second_candidate.is_selected is False


def test_select_candidate_blocks_duplicate_candidate_user_in_same_batch(
    auth_client,
    matchmaker_staff,
    ready_user,
    candidate_user,
):
    ready_user.pool_status = CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["pool_status", "owner", "updated_at"])
    batch = RecommendationBatch.objects.create(
        user=ready_user,
        staff=matchmaker_staff,
        batch_no="REC-20260316-DUP-1",
        candidate_count=2,
        status=RecommendationBatch.STATUS_OPEN,
    )
    first_record = RecommendationCandidate.objects.create(batch=batch, candidate_user=candidate_user)
    duplicate_record = RecommendationCandidate.objects.create(batch=batch, candidate_user=candidate_user)

    client = auth_client(matchmaker_staff)
    first_resp = client.post(f"/api/v1/recommendations/candidates/{first_record.id}/select/")
    assert first_resp.status_code == 200

    second_resp = client.post(f"/api/v1/recommendations/candidates/{duplicate_record.id}/select/")
    assert second_resp.status_code == 400
    assert second_resp.json()["code"] == "BATCH_ALREADY_HAS_SELECTED_CANDIDATE"

    first_record.refresh_from_db()
    duplicate_record.refresh_from_db()
    assert first_record.is_selected is True
    assert duplicate_record.is_selected is False


def test_select_same_candidate_user_in_different_batches_still_allowed(
    auth_client,
    matchmaker_staff,
    ready_user,
    candidate_user,
):
    ready_user.pool_status = CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["pool_status", "owner", "updated_at"])
    batch1 = RecommendationBatch.objects.create(
        user=ready_user,
        staff=matchmaker_staff,
        batch_no="REC-20260316-B1",
        candidate_count=1,
        status=RecommendationBatch.STATUS_OPEN,
    )
    batch2 = RecommendationBatch.objects.create(
        user=ready_user,
        staff=matchmaker_staff,
        batch_no="REC-20260316-B2",
        candidate_count=1,
        status=RecommendationBatch.STATUS_OPEN,
    )
    candidate1 = RecommendationCandidate.objects.create(batch=batch1, candidate_user=candidate_user)
    candidate2 = RecommendationCandidate.objects.create(batch=batch2, candidate_user=candidate_user)

    client = auth_client(matchmaker_staff)
    resp1 = client.post(f"/api/v1/recommendations/candidates/{candidate1.id}/select/")
    resp2 = client.post(f"/api/v1/recommendations/candidates/{candidate2.id}/select/")

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    candidate1.refresh_from_db()
    candidate2.refresh_from_db()
    assert candidate1.is_selected is True
    assert candidate2.is_selected is True


def test_select_candidate_on_closed_batch(auth_client, matchmaker_staff, ready_user, candidate_user):
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["owner", "updated_at"])
    batch, candidate = _create_open_batch(ready_user, matchmaker_staff, candidate_user)
    batch.status = RecommendationBatch.STATUS_CLOSED
    batch.save(update_fields=["status"])

    client = auth_client(matchmaker_staff)
    resp = client.post(f"/api/v1/recommendations/candidates/{candidate.id}/select/")
    assert resp.status_code == 400
    assert resp.json()["code"] == "BATCH_CLOSED"


def test_select_candidate_permission_denied(auth_client, create_staff, ready_user, candidate_user, matchmaker_staff):
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["owner", "updated_at"])
    batch, candidate = _create_open_batch(ready_user, matchmaker_staff, candidate_user)

    other_matchmaker = create_staff(name="其他红娘")
    client = auth_client(other_matchmaker)
    resp = client.post(f"/api/v1/recommendations/candidates/{candidate.id}/select/")
    assert resp.status_code == 403


def _prepare_ready_user(owner, ready_user):
    ready_user.owner = owner
    ready_user.save(update_fields=["owner", "updated_at"])
    return ready_user


def test_create_batch_rejects_duplicate_input(
    auth_client, matchmaker_staff, ready_user, candidate_user
):
    client = auth_client(matchmaker_staff)
    _prepare_ready_user(matchmaker_staff, ready_user)

    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": ready_user.id, "candidate_user_ids": [candidate_user.id, candidate_user.id]},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CANDIDATE_DUPLICATE_INPUT"


def test_create_batch_rejects_invalid_candidate_id(
    auth_client, matchmaker_staff, ready_user
):
    client = auth_client(matchmaker_staff)
    _prepare_ready_user(matchmaker_staff, ready_user)

    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": ready_user.id, "candidate_user_ids": [99999]},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CANDIDATE_NOT_FOUND"


def test_create_batch_rejects_paused_candidate(
    auth_client, matchmaker_staff, ready_user, create_customer_profile
):
    client = auth_client(matchmaker_staff)
    _prepare_ready_user(matchmaker_staff, ready_user)
    paused_candidate = create_customer_profile(
        pool_status=CustomerProfile.STATUS_PAUSED, gender=CustomerProfile.GENDER_FEMALE
    )

    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": ready_user.id, "candidate_user_ids": [paused_candidate.id]},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CANDIDATE_PAUSED"


def test_create_batch_rejects_candidate_in_match(
    auth_client, matchmaker_staff, ready_user, create_customer_profile
):
    client = auth_client(matchmaker_staff)
    _prepare_ready_user(matchmaker_staff, ready_user)
    matched_candidate = create_customer_profile(
        pool_status=CustomerProfile.STATUS_SELECTED_PENDING_MEET,
        is_in_match=True,
        gender=CustomerProfile.GENDER_FEMALE,
    )

    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": ready_user.id, "candidate_user_ids": [matched_candidate.id]},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CANDIDATE_IN_MATCH"


def test_create_batch_rejects_deleted_candidate(
    auth_client, matchmaker_staff, ready_user, create_customer_profile
):
    client = auth_client(matchmaker_staff)
    _prepare_ready_user(matchmaker_staff, ready_user)
    deleted_candidate = create_customer_profile(gender=CustomerProfile.GENDER_FEMALE)
    deleted_candidate.deleted_at = timezone.now()
    deleted_candidate.save(update_fields=["deleted_at"])

    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": ready_user.id, "candidate_user_ids": [deleted_candidate.id]},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CANDIDATE_DELETED"


def test_create_batch_rejects_same_gender_candidate(
    auth_client, matchmaker_staff, ready_user, create_customer_profile
):
    client = auth_client(matchmaker_staff)
    _prepare_ready_user(matchmaker_staff, ready_user)
    wrong_gender_candidate = create_customer_profile(gender=ready_user.gender)

    resp = client.post(
        "/api/v1/recommendations/",
        data={"user_id": ready_user.id, "candidate_user_ids": [wrong_gender_candidate.id]},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CANDIDATE_GENDER_MISMATCH"


# ---------------------------------------------------------------------------
# POST /api/v1/recommendations/{batch_id}/close/
# ---------------------------------------------------------------------------

def test_close_batch_with_selected_candidate(auth_client, matchmaker_staff, ready_user, candidate_user):
    ready_user.pool_status = CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["pool_status", "owner", "updated_at"])
    batch, candidate = _create_open_batch(ready_user, matchmaker_staff, candidate_user)
    candidate.is_selected = True
    candidate.save(update_fields=["is_selected", "updated_at"])

    client = auth_client(matchmaker_staff)
    resp = client.post(f"/api/v1/recommendations/{batch.id}/close/")
    assert resp.status_code == 200
    assert resp.json()["status"] == RecommendationBatch.STATUS_CLOSED

    ready_user.refresh_from_db()
    # Status should NOT be reverted because a candidate was selected
    assert ready_user.pool_status == CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT


def test_close_batch_no_selection_reverts_user_status(auth_client, matchmaker_staff, ready_user, candidate_user):
    """BR-REC-005: no selected candidate → revert user to communicated_pending_recommend + add tag."""
    ready_user.pool_status = CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["pool_status", "owner", "updated_at"])
    batch, _ = _create_open_batch(ready_user, matchmaker_staff, candidate_user)

    old_last_action = ready_user.last_action_at
    old_last_unmatched = ready_user.last_unmatched_active_at

    client = auth_client(matchmaker_staff)
    resp = client.post(f"/api/v1/recommendations/{batch.id}/close/")
    assert resp.status_code == 200

    ready_user.refresh_from_db()
    assert ready_user.pool_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    assert "待重新推荐" in (ready_user.tags or [])
    assert ready_user.last_action_at is not None
    assert ready_user.last_unmatched_active_at is not None
    if old_last_action is not None:
        assert ready_user.last_action_at > old_last_action
    if old_last_unmatched is not None:
        assert ready_user.last_unmatched_active_at > old_last_unmatched
    history = UserStatusHistory.objects.filter(user=ready_user).order_by("-created_at").first()
    assert history.to_status == CustomerProfile.STATUS_COMMUNICATED_PENDING_RECOMMEND
    assert history.reason == "推荐批次关闭"


def test_close_batch_no_selection_tag_not_duplicated(auth_client, matchmaker_staff, ready_user, candidate_user):
    """BR-REC-005: 关闭无选中批次时，'待重新推荐' 标签不重复追加。"""
    ready_user.pool_status = CustomerProfile.STATUS_RECOMMENDED_PENDING_SELECT
    ready_user.tags = ["待重新推荐"]
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["pool_status", "tags", "owner", "updated_at"])
    batch, _ = _create_open_batch(ready_user, matchmaker_staff, candidate_user)

    client = auth_client(matchmaker_staff)
    client.post(f"/api/v1/recommendations/{batch.id}/close/")

    ready_user.refresh_from_db()
    assert ready_user.tags.count("待重新推荐") == 1


def test_close_batch_already_closed(auth_client, matchmaker_staff, ready_user, candidate_user):
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["owner", "updated_at"])
    batch, _ = _create_open_batch(ready_user, matchmaker_staff, candidate_user)
    batch.status = RecommendationBatch.STATUS_CLOSED
    batch.save(update_fields=["status"])

    client = auth_client(matchmaker_staff)
    resp = client.post(f"/api/v1/recommendations/{batch.id}/close/")
    assert resp.status_code == 400
    assert resp.json()["code"] == "BATCH_ALREADY_CLOSED"


# ---------------------------------------------------------------------------
# GET /api/v1/recommendations/?user_id=
# ---------------------------------------------------------------------------

def test_list_batches_filtered_by_user(auth_client, matchmaker_staff, ready_user, candidate_user):
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["owner", "updated_at"])
    batch, _ = _create_open_batch(ready_user, matchmaker_staff, candidate_user)

    client = auth_client(matchmaker_staff)
    resp = client.get(f"/api/v1/recommendations/?user_id={ready_user.id}")
    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()]
    assert batch.id in ids


def test_matchmaker_only_sees_own_batches(
    auth_client, create_staff, ready_user, candidate_user, matchmaker_staff
):
    other_staff = create_staff(name="其他红娘")
    # batch created by matchmaker_staff
    ready_user.owner = matchmaker_staff
    ready_user.save(update_fields=["owner", "updated_at"])
    batch, _ = _create_open_batch(ready_user, matchmaker_staff, candidate_user)

    client = auth_client(other_staff)
    resp = client.get("/api/v1/recommendations/")
    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()]
    assert batch.id not in ids


def test_current_owner_can_see_recommendation_history_created_by_other_matchmaker(
    auth_client, create_staff, ready_user, candidate_user
):
    creator = create_staff(name="原发起红娘")
    current_owner = create_staff(name="当前owner红娘")
    ready_user.owner = current_owner
    ready_user.save(update_fields=["owner", "updated_at"])
    batch, _ = _create_open_batch(ready_user, creator, candidate_user)

    resp = auth_client(current_owner).get(f"/api/v1/recommendations/?user_id={ready_user.id}")

    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()]
    assert batch.id in ids


def test_admin_can_see_recommendation_history_for_any_user(
    auth_client, admin_staff, create_staff, ready_user, candidate_user
):
    creator = create_staff(name="推荐创建红娘")
    batch, _ = _create_open_batch(ready_user, creator, candidate_user)

    resp = auth_client(admin_staff).get(f"/api/v1/recommendations/?user_id={ready_user.id}")

    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()]
    assert batch.id in ids


def test_recommendation_history_response_structure_unchanged_for_owner(
    auth_client, create_staff, ready_user, candidate_user
):
    creator = create_staff(name="创建者红娘")
    current_owner = create_staff(name="owner红娘")
    ready_user.owner = current_owner
    ready_user.save(update_fields=["owner", "updated_at"])
    batch, _ = _create_open_batch(ready_user, creator, candidate_user)

    resp = auth_client(current_owner).get(f"/api/v1/recommendations/?user_id={ready_user.id}")

    assert resp.status_code == 200
    item = next(record for record in resp.json() if record["id"] == batch.id)
    assert "id" in item
    assert "user_id" in item
    assert "user_name" in item
    assert "staff_id" in item
    assert "staff_name" in item
    assert "batch_no" in item
    assert "candidate_count" in item
    assert "status" in item
    assert "candidates" in item
