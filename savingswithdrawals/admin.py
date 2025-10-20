from django.contrib import admin

from savingswithdrawals.models import SavingsWithdrawal


class SavingsWithdrawalAdmin(admin.ModelAdmin):
    list_display = (
        "withdrawn_by",
        "amount",
        "savings_account",
        "created_at",
        "transaction_status",
    )
    search_fields = ("withdrawn_by__member_no", "savings_account__account_number")
    list_filter = ("created_at", "transaction_status")
    ordering = ["-created_at"]


admin.site.register(SavingsWithdrawal, SavingsWithdrawalAdmin)
