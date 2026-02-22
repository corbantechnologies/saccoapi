from django.urls import path

from feespayments.views import (
    FeePaymentListCreateView,
    FeePaymentView,
    BulkFeePaymentView,
    BulkFeePaymentUploadView,
)

app_name = "feespayments"

urlpatterns = [
    path("", FeePaymentListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", FeePaymentView.as_view(), name="detail"),
    path("bulk/", BulkFeePaymentView.as_view(), name="bulk-create"),
    path("bulk/upload/", BulkFeePaymentUploadView.as_view(), name="bulk-upload"),
]
