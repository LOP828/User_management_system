from django.urls import path

from apps.staff.views import StaffDetailView, StaffListCreateView, StaffMeView

urlpatterns = [
    path("me/", StaffMeView.as_view(), name="staff-me"),
    path("", StaffListCreateView.as_view(), name="staff-list-create"),
    path("<int:pk>/", StaffDetailView.as_view(), name="staff-detail"),
]
