from django.contrib import admin

from loandisbursements.models import LoanDisbursement


class LoanDisbursementAdmin(admin.ModelAdmin):
    list_display = (
        "loan_account",
        "disbursement_type",
        "amount",
        "transaction_status",
        "created_at",
    )
    list_filter = (
        "loan_account",
        "disbursement_type",
        "transaction_status",
        "created_at",
    )
    search_fields = ("loan_account__account_number", "disbursement_type")
    ordering = ["-created_at"]


admin.site.register(LoanDisbursement)
