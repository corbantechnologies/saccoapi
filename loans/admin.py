from django.contrib import admin

from loans.models import LoanAccount


class LoanAccountAdmin(admin.ModelAdmin):
    list_display = (
        "account_number",
        "member",
        "loan_type",
        "is_active",
    )
    search_fields = ("account_number", "member__member_no")
    list_filter = ("is_active", "created_at", "updated_at")
    ordering = ("-created_at",)


admin.site.register(LoanAccount, LoanAccountAdmin)
