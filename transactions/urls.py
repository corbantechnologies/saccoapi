from django.urls import path

from transactions.views import AccountListView

app_name = "transactions"

urlpatterns = [
    path("", AccountListView.as_view(), name="transaction-list-create"),
]
