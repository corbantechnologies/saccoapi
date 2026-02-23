from django.urls import path

from feetypes.views import FeeTypeListCreateView, FeeTypeDetailView 

app_name = "feetypes"

urlpatterns = [
    path("", FeeTypeListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", FeeTypeDetailView.as_view(), name="detail"),
]