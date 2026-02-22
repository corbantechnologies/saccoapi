from django.contrib import admin

from feetypes.models import FeeType

class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "standard_amount", "description", "created_at", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("created_at", "updated_at", "is_active")
    ordering = ("-created_at",)

admin.site.register(FeeType, FeeTypeAdmin)

