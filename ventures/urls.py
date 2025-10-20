from django.urls import path

from ventures.views import VentureAccountDetailView, VentureAccountListCreateView

app_name = "ventures"

urlpatterns = [
    path("", VentureAccountListCreateView.as_view(), name="ventures"),
    path("<str:identity>/", VentureAccountDetailView.as_view(), name="venture-detail"),
]
