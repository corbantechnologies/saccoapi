from django.urls import path

from transactions.views import (
    AccountListView,
    AccountListDownloadView,
    AccountDetailView,
    CombinedBulkUploadView,
    MemberYearlySummaryView,
    MemberYearlySummaryPDFView,
    SACCOSummaryView,
    CashbookView,
    SACCOSummaryPDFView
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
    path("<str:member_no>/summary/", MemberYearlySummaryView.as_view(), name="summary"),
    path("<str:member_no>/summary/download/", MemberYearlySummaryPDFView.as_view(), name="summary-pdf"),
    
    # SACCO Level Reports
    path("sacco/reports/", SACCOSummaryView.as_view(), name="sacco-summary"),
    path("sacco/reports/download/", SACCOSummaryPDFView.as_view(), name="sacco-summary-pdf"),
    path("sacco/cashbook/", CashbookView.as_view(), name="sacco-cashbook"),
]
