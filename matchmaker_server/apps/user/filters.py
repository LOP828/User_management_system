import django_filters

from apps.user.models import CustomerProfile


class CustomerProfileFilterSet(django_filters.FilterSet):
    payment_level_id = django_filters.NumberFilter(field_name="payment_level_id")
    owner_id = django_filters.NumberFilter(field_name="owner_id")
    is_profile_complete = django_filters.BooleanFilter(field_name="is_profile_complete")
    is_in_match = django_filters.BooleanFilter(field_name="is_in_match")
    created_at_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_at_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    tag = django_filters.CharFilter(method="filter_tag")

    class Meta:
        model = CustomerProfile
        fields = (
            "pool_status",
            "payment_level_id",
            "owner_id",
            "is_profile_complete",
            "is_in_match",
        )

    def filter_tag(self, queryset, name, value):
        return queryset.filter(tags__contains=[value])
