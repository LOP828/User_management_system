from django.urls import path

from apps.dashboard.views import AdminDashboardView, MatchmakerDashboardView

urlpatterns = [
    path("matchmaker/", MatchmakerDashboardView.as_view(), name="dashboard-matchmaker"),
    path("admin/", AdminDashboardView.as_view(), name="dashboard-admin"),
]
