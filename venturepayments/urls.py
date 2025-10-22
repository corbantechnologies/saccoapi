from django.urls import path

from venturepayments.views import VenturePaymentListCreateView, VenturePaymentDetailView, VenturePaymentBulkUploadView

app_name = "venturepayments"

urlpatterns = [
    path("", VenturePaymentListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", VenturePaymentDetailView.as_view(), name="detail"),
    path("bulk/upload/", VenturePaymentBulkUploadView.as_view(), name="bulk-upload"),
]
