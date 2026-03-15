from apps.staff.models import Staff


MATCHCARD_EDITABLE_FIELDS = {
    "male_feedback",
    "male_heat",
    "female_feedback",
    "female_heat",
    "staff_judgment",
}


def can_view_match_card(actor, match_card):
    if actor.role == Staff.ROLE_ADMIN:
        return True
    return actor.id in {
        match_card.male_staff_id,
        match_card.female_staff_id,
        match_card.primary_staff_id,
    }


def get_allowed_update_fields(actor, match_card):
    if actor.role == Staff.ROLE_ADMIN:
        return MATCHCARD_EDITABLE_FIELDS
    if actor.id == match_card.primary_staff_id:
        return MATCHCARD_EDITABLE_FIELDS
    if actor.id == match_card.male_staff_id:
        return {"male_feedback", "male_heat"}
    if actor.id == match_card.female_staff_id:
        return {"female_feedback", "female_heat"}
    return set()
