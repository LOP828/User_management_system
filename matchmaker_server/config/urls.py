from django.urls import include, path

urlpatterns = [
    path("api/v1/auth/", include("apps.staff.auth_urls")),
    path("api/v1/staff/", include("apps.staff.urls")),
    path("api/v1/users/", include("apps.user.urls")),
    path("api/v1/recommendations/", include("apps.recommendation.urls")),
    path("api/v1/match-cards/", include("apps.matchcard.urls")),
    path("api/v1/follow-ups/", include("apps.followup.urls")),
    path("api/v1/success-applications/", include("apps.success.urls")),
    path("api/v1/success-cases/", include("apps.success.case_urls")),
    path("api/v1/transfer-requests/", include("apps.transfer.urls")),
    path("api/v1/reminders/", include("apps.reminder.urls")),
    path("api/v1/dashboard/", include("apps.dashboard.urls")),
    path("api/v1/oplogs/", include("apps.oplog.urls")),
    path("api/v1/", include("apps.config_mgmt.urls")),
    path("api/v1/search/", include("apps.search.urls")),
]
