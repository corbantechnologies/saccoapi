from django.contrib import admin

from venturepayments.models import VenturePayment


class VenturePaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "venture_account",
        "amount",
        "payment_method",
        "payment_type",
        "transaction_status",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "reference",
        "venture_account__account_number",
        "amount",
        "paid_by__member_no",
        "payment_method",
    )

    list_filter = (
        "venture_account",
        "payment_method",
        "payment_type",
        "transaction_status",
    )

    ordering = ["-created_at"]


admin.site.register(VenturePayment, VenturePaymentAdmin)
