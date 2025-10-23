from django.urls import path

from transactions.views import (
    AccountListView,
    AccountListDownloadView,
    AccountDetailView,
    CombinedBulkUploadView,
)

app_name = "transactions"

urlpatterns = [
    path("", AccountListView.as_view(), name="transaction-list-create"),
    path("<str:member_no>/", AccountDetailView.as_view(), name="transaction-detail"),
    path(
        "list/download/",
        AccountListDownloadView.as_view(),
        name="transaction-list-download",
    ),
    path(
        "bulk/upload/",
        CombinedBulkUploadView.as_view(),
        name="combined-bulk-upload",
    ),
]
