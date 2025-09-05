from django.urls import path

from savingstypes.views import SavingTypeListCreateView, SavingsTypeDetailView

app_name = "savingstypes"

urlpatterns = [
    path("", SavingTypeListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", SavingsTypeDetailView.as_view(), name="detail"),
]
