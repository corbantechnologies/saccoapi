from django.contrib import admin

from memberfees.models import MemberFee

class MemberFeeAdmin(admin.ModelAdmin):
    list_display = ("member", "fee_type", "amount", "account_number", "is_paid", "created_at", "updated_at")
    search_fields = ("member", "fee_type")
    list_filter = ("created_at", "updated_at", "is_paid")
    ordering = ("-created_at",)

admin.site.register(MemberFee, MemberFeeAdmin)
