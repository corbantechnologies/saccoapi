from django.urls import path

from loantypes.views import LoanTypeListCreateView, LoanTypeDetailView

app_name = "loantypes"

urlpatterns = [
    path("", LoanTypeListCreateView.as_view(), name="loantype-list-create"),
    path("<str:reference>/", LoanTypeDetailView.as_view(), name="loantype-detail"),
]
