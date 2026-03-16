from django.urls import path

from apps.oplog.views import OperationLogListView

urlpatterns = [
    path("", OperationLogListView.as_view(), name="operation-log-list"),
]
