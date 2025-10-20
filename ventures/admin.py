from django.contrib import admin

from ventures.models import VentureAccount


class VentureAccountAdmin(admin.ModelAdmin):
    list_display = ("member", "venture_type", "account_number", "balance", "is_active")
    search_fields = ("member__member_no", "account_number")
    list_filter = ("created_at", "updated_at")
    ordering = ("-created_at",)


admin.site.register(VentureAccount, VentureAccountAdmin)
