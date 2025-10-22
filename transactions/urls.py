from django.urls import path

from transactions.views import AccountListView, AccountListDownloadView

app_name = "transactions"

urlpatterns = [
    path("", AccountListView.as_view(), name="transaction-list-create"),
    path("list/download/", AccountListDownloadView.as_view(), name="transaction-list-download"),
]
