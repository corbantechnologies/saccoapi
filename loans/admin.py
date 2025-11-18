from django.contrib import admin

from loans.models import LoanAccount


class LoanAccountAdmin(admin.ModelAdmin):
    list_display = (
        "account_number",
        "user",
        "loan_type",
        "loan_amount",
        "is_approved",
        "is_active",
    )
    search_fields = ("account_number", "user__member_no")
    list_filter = ("is_approved", "is_active", "created_at", "updated_at")
    ordering = ("-created_at",)


admin.site.register(LoanAccount, LoanAccountAdmin)
