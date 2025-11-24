from django.urls import path

from loanapplications.views import (
    LoanApplicationListCreateView,
    LoanApplicationDetailView,
    SubmitLoanApplicationView,
    ApproveOrDeclineLoanApplicationView,
    LoanApplicationListView,
    SubmitForAmendmentView,
    AdminAmendView,
    MemberAcceptAmendmentView,
    MemberCancelAmendmentView,
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
    path(
        "<str:reference>/submit-amendment/",
        SubmitForAmendmentView.as_view(),
        name="submit-for-amendment",
    ),
    path(
        "<str:reference>/amend/",
        AdminAmendView.as_view(),
        name="admin-amend",
    ),
    path(
        "<str:reference>/accept-amendment/",
        MemberAcceptAmendmentView.as_view(),
        name="accept-amendment",
    ),
    path(
        "<str:reference>/cancel-amendment/",
        MemberCancelAmendmentView.as_view(),
        name="cancel-amendment",
    ),
]
