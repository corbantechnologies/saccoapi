from django.urls import path

from loans.views import (
    LoanAccountListCreateView,
    LoanAccountDetailView,
    LoanAccountCreateByAdminView,
)

app_name = "loans"

urlpatterns = [
    path("", LoanAccountListCreateView.as_view(), name="loan-account-list-create"),
    path(
        "<str:identity>/",
        LoanAccountDetailView.as_view(),
        name="loan-account-detail",
    ),
    path(
        "create/loan/",
        LoanAccountCreateByAdminView.as_view(),
        name="loan-account-create-by-admin",
    ),
]
