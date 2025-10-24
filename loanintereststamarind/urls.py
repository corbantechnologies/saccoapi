from django.urls import path

from loanintereststamarind.views import (
    TamarindLoanInterestDetailView,
    TamarindLoanInterestListCreateView,
)

app_name = "loanintereststamarind"

urlpatterns = [
    path(
        "",
        TamarindLoanInterestListCreateView.as_view(),
        name="loaninterest-list-create",
    ),
    path(
        "<str:reference>/",
        TamarindLoanInterestDetailView.as_view(),
        name="loaninterest-detail",
    ),
]
