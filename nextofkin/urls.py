from django.urls import path

from nextofkin.views import NextOfKinDetailView, NextOfKinListCreateView

app_name = "nextofkin"

urlpatterns = [
    path("", NextOfKinListCreateView.as_view(), name="nextofkin-list-create"),
    path("<str:reference>/", NextOfKinDetailView.as_view(), name="nextofkin-detail")
]