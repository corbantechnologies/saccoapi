from django.urls import path

from venturedeposits.views import VentureDepositListCreateView, VentureDepositDetailView

app_name = "venturedeposits"

urlpatterns = [
    path("", VentureDepositListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", VentureDepositDetailView.as_view(), name="detail"),
]
