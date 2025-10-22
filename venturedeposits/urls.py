from django.urls import path

from venturedeposits.views import (
    VentureDepositListCreateView,
    VentureDepositDetailView,
    VentureDepositBulkUploadView,
)

app_name = "venturedeposits"

urlpatterns = [
    path("", VentureDepositListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", VentureDepositDetailView.as_view(), name="detail"),
    path(
        "bulk/upload/",
        VentureDepositBulkUploadView.as_view(),
        name="bulk-upload",
    ),
]
