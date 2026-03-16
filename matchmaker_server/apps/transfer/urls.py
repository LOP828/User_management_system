from django.urls import path

from apps.transfer.views import (
    TransferRequestApproveView,
    TransferRequestListCreateView,
    TransferRequestRejectView,
)

urlpatterns = [
    path("", TransferRequestListCreateView.as_view(), name="transfer-request-list-create"),
    path("<int:transfer_id>/approve/", TransferRequestApproveView.as_view(), name="transfer-request-approve"),
    path("<int:transfer_id>/reject/", TransferRequestRejectView.as_view(), name="transfer-request-reject"),
]
