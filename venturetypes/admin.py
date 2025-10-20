from django.contrib import admin

from venturetypes.models import VentureType


class VentureTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "interest_rate")
    search_fields = ("name",)
    list_filter = ("created_at", "updated_at")
    ordering = ("-created_at",)


admin.site.register(VentureType, VentureTypeAdmin)
