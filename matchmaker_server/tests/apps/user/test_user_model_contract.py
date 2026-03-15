from apps.user.models import CustomerProfile, UserStatusHistory


def test_customer_profile_meta_contract():
    assert CustomerProfile._meta.db_table == "user"
    assert CustomerProfile._meta.get_field("pool_status").default == "new_pending"
    assert CustomerProfile._meta.get_field("is_profile_complete").default is False
    assert CustomerProfile._meta.get_field("is_in_match").default is False


def test_customer_profile_json_fields_allow_null():
    assert CustomerProfile._meta.get_field("profile_detail").null is True
    assert CustomerProfile._meta.get_field("emotional_history").null is True
    assert CustomerProfile._meta.get_field("tags").null is True


def test_user_status_history_meta_contract():
    assert UserStatusHistory._meta.db_table == "user_status_history"
    assert UserStatusHistory._meta.get_field("changed_by").target_field.name == "id"
    assert UserStatusHistory._meta.get_field("reason_id").null is True
