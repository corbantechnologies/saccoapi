from django.contrib import admin

from savingsdeposits.models import SavingsDeposit


class SavingsDepositAdmin(admin.ModelAdmin):
    list_display = (
        "savings_account",
        "deposited_by",
        "amount",
        "payment_method",
        "deposit_type",
        "transaction_status",
        "created_at",
    )
    list_filter = ("payment_method", "deposit_type", "transaction_status", "created_at")
    search_fields = (
        "savings_account__account_number",
        "deposited_by__member_no",
        "phone_number",
    )
    readonly_fields = ("created_at", "updated_at", "identity", "reference")
    ordering = ("-created_at",)


admin.site.register(SavingsDeposit, SavingsDepositAdmin)
