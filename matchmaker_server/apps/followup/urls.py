from django.urls import path

from apps.followup.views import FollowUpDetailView, FollowUpListCreateView


urlpatterns = [
    path("", FollowUpListCreateView.as_view(), name="followup-list-create"),
    path("<int:pk>/", FollowUpDetailView.as_view(), name="followup-detail"),
]
