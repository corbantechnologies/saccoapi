from django.urls import path

from guaranteerequests.views import (
    GuaranteeRequestListCreateView,
    GuaranteeRequestRetrieveView,
    GuaranteeRequestUpdateStatusView,
)

app_name = "guaranteerequests"

urlpatterns = [
    path("", GuaranteeRequestListCreateView.as_view(), name="guaranteerequests"),
    path(
        "<str:reference>/",
        GuaranteeRequestRetrieveView.as_view(),
        name="guarantee-request-detail",
    ),
    path(
        "<str:reference>/status/",
        GuaranteeRequestUpdateStatusView.as_view(),
        name="guarantee-request-update-status",
    ),
]
