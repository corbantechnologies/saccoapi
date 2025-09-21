from django.urls import path

from savingsdeposits.views import SavingsDepositListCreateView, SavingsDepositView

app_name = "savingsdeposits"

urlpatterns = [
    path("", SavingsDepositListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", SavingsDepositView.as_view(), name="detail"),
]
