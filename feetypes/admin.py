from django.contrib import admin

from feetypes.models import FeeType

class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "standard_amount", "is_income", "is_expense", "is_liability", "is_asset", "is_equity", "description", "created_at", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("created_at", "updated_at", "is_active", "is_income", "is_expense", "is_liability", "is_asset", "is_equity")
    ordering = ("-created_at",)

admin.site.register(FeeType, FeeTypeAdmin)

