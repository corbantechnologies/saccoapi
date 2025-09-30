from django.urls import path

from loans.views import LoanAccountListCreateView, LoanAccountDetailView

app_name = "loans"

urlpatterns = [
    path("", LoanAccountListCreateView.as_view(), name="loan-account-list-create"),
    path(
        "<str:identity>/",
        LoanAccountDetailView.as_view(),
        name="loan-account-detail",
    ),
]
