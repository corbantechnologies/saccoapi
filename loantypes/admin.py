from django.contrib import admin

from loantypes.models import LoanType


class LoanTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")
    list_filter = ("created_at", "updated_at")
    ordering = ("-created_at",)


admin.site.register(LoanType, LoanTypeAdmin)
