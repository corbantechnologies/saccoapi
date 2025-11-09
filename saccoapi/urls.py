from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/nextofkins/", include("nextofkin.urls")),
    path("api/v1/savingstypes/", include("savingstypes.urls")),
    path("api/v1/loantypes/", include("loantypes.urls")),
    path("api/v1/savings/", include("savings.urls")),
    path("api/v1/savingsdeposits/", include("savingsdeposits.urls")),
    path("api/v1/loans/", include("loans.urls")),
    path("api/v1/loanrepayments/", include("loanrepayments.urls")),
    path("api/v1/savingswithdrawals/", include("savingswithdrawals.urls")),
    path("api/v1/venturetypes/", include("venturetypes.urls")),
    path("api/v1/ventures/", include("ventures.urls")),
    path("api/v1/venturedeposits/", include("venturedeposits.urls")),
    path("api/v1/venturepayments/", include("venturepayments.urls")),
    path("api/v1/transactions/", include("transactions.urls")),
    path("api/v1/tamarindloaninterests/", include("loanintereststamarind.urls")),
]
