from django.urls import path

from loanrepayments.views import (
    LoanRepaymentListCreateView,
    LoanRepaymentDetailView,
    LoanRepaymentBulkUploadView,
)

app_name = "loanrepayments"

urlpatterns = [
    path("", LoanRepaymentListCreateView.as_view(), name="loanrepayment-list-create"),
    path(
        "<str:reference>/",
        LoanRepaymentDetailView.as_view(),
        name="loanrepayment-detail",
    ),
    path(
        "bulk/upload/",
        LoanRepaymentBulkUploadView.as_view(),
        name="loanrepayment-bulk-upload",
    ),
]
