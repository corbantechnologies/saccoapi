from django.urls import path

from loandisbursements.views import (
    LoanDisbursementListCreateView,
    LoanDisbursementDetailView,
    LoanDisbursementCSVUploadView,
    BulkLoanDisbursementView,
)

app_name = "loandisbursements"

urlpatterns = [
    path("", LoanDisbursementListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", LoanDisbursementDetailView.as_view(), name="detail"),
    path("bulk/upload/", LoanDisbursementCSVUploadView.as_view(), name="bulk-upload"),
    path("bulk/", BulkLoanDisbursementView.as_view(), name="bulk-create"),
]
