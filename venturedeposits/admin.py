from django.contrib import admin

from venturedeposits.models import VentureDeposit


class VentureDepositAdmin(admin.ModelAdmin):
    list_display = ("venture_account", "amount", "created_at", "deposited_by")
    list_filter = ("created_at",)
    search_fields = (
        "venture_account",
        "deposited_by__member_no",
        "venture_account__account_number",
    )
    ordering = ("-created_at",)


admin.site.register(VentureDeposit, VentureDepositAdmin)
