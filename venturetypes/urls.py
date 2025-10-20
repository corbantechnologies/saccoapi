from django.urls import path

from venturetypes.views import VentureTypeListCreateView, VentureTypeDetailView

app_name = "venturetypes"

urlpatterns = [
    path("", VentureTypeListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", VentureTypeDetailView.as_view(), name="detail"),
]
