from django.urls import path

from apps.success.views import SuccessCaseDetailView, SuccessCaseInvalidateView, SuccessCaseListView


urlpatterns = [
    path("", SuccessCaseListView.as_view(), name="success-case-list"),
    path("<int:pk>/", SuccessCaseDetailView.as_view(), name="success-case-detail"),
    path("<int:pk>/invalidate/", SuccessCaseInvalidateView.as_view(), name="success-case-invalidate"),
]
