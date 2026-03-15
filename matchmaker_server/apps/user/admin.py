from django.contrib import admin

from apps.user.models import CustomerProfile, UserStatusHistory


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "pool_status", "is_in_match", "paid_at", "last_action_at")
    search_fields = ("name", "phone", "wechat")
    list_filter = ("pool_status", "is_in_match", "city")


@admin.register(UserStatusHistory)
class UserStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "from_status", "to_status", "changed_by", "created_at")
    list_filter = ("to_status",)
