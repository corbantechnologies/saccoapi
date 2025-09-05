from django.contrib import admin

from savingstypes.models import SavingsType


class SavingsTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("created_at", "updated_at")
    ordering = ("-created_at",)

admin.site.register(SavingsType, SavingsTypeAdmin)
