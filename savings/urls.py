from django.urls import path

from savings.views import SavingsAccountDetailView, SavingsAccountListCreateView

app_name = "savings"

urlpatterns = [
    path(
        "", SavingsAccountListCreateView.as_view(), name="savings-account-list-create"
    ),
    path(
        "<str:identity>/",
        SavingsAccountDetailView.as_view(),
        name="savings-account-detail",
    ),
]
