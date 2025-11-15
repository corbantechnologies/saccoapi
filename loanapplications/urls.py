from django.urls import path

from loanapplications.views import (
    LoanApplicationListCreateView,
    LoanApplicationDetailView,
)

app_name = "loanapplications"

urlpatterns = [
    path("", LoanApplicationListCreateView.as_view(), name="loanapplications"),
    path(
        "<str:reference>/",
        LoanApplicationDetailView.as_view(),
        name="loanapplication-detail",
    ),
]
