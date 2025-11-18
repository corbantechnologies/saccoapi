from django.urls import path

from guarantorprofile.views import (
    GuarantorProfileListCreateView,
    GuarantorProfileDetailView,
)

app_name = "guarantorprofile"

urlpatterns = [
    path(
        "",
        GuarantorProfileListCreateView.as_view(),
        name="guarantorprofile-list-create",
    ),
    path(
        "<str:member__member_no>/",
        GuarantorProfileDetailView.as_view(),
        name="guarantorprofile-detail",
    ),
]
