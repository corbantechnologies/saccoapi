from django.urls import path

from loanapplications.views import (
    LoanApplicationListCreateView,
    LoanApplicationDetailView,
    SubmitLoanApplicationView,
    ApproveOrDeclineLoanApplicationView,
    LoanApplicationListView,
)

app_name = "loanapplications"

urlpatterns = [
    path("", LoanApplicationListView.as_view(), name="loanapplications-list"),
    path("list/", LoanApplicationListCreateView.as_view(), name="loanapplications"),
    path(
        "<str:reference>/",
        LoanApplicationDetailView.as_view(),
        name="loanapplication-detail",
    ),
    path(
        "<str:reference>/submit/",
        SubmitLoanApplicationView.as_view(),
        name="submit-loanapplication",
    ),
    path(
        "<str:reference>/status/",
        ApproveOrDeclineLoanApplicationView.as_view(),
        name="approve-or-decline-loanapplication",
    ),
]
