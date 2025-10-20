from django.contrib import admin

from savings.models import SavingsAccount


class SavingsAccountAdmin(admin.ModelAdmin):
    list_display = ("account_number", "member", "account_type", "balance", "is_active")
    search_fields = ("account_number", "member__member_no")
    list_filter = ("account_type", "is_active", "created_at", "updated_at")
    ordering = ("-created_at",)


admin.site.register(SavingsAccount, SavingsAccountAdmin)
