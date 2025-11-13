from django.contrib import admin

from loanapplications.models import LoanApplication


class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "product",
        "requested_amount",
        "status",
        "created_at",
        "calculation_mode",
    )
    list_filter = ("status", "calculation_mode")
    search_fields = ("member__member_no", "product__name")


admin.site.register(LoanApplication, LoanApplicationAdmin)
