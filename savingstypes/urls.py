from django.urls import path

from savingstypes.views import SavingsTypeListCreateView, SavingsTypeDetailView

app_name = "savingstypes"

urlpatterns = [
    path("", SavingsTypeListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", SavingsTypeDetailView.as_view(), name="detail"),
]
