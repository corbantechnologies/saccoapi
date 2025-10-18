from django.urls import path

from savingswithdrawals.views import (
    SavingsWithdrawalListCreateView,
    SavingsWithdrawalDetailView,
    SavingsWithdrawalUpdateView,
)

app_name = "savingswithdrawals"

urlpatterns = [
    path("", SavingsWithdrawalListCreateView.as_view(), name="withdrawal-list-create"),
    path(
        "<str:reference>/",
        SavingsWithdrawalDetailView.as_view(),
        name="withdrawal-detail",
    ),
    path(
        "<str:identity>/",
        SavingsWithdrawalUpdateView.as_view(),
        name="withdrawal-update",
    ),
]
