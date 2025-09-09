from django.contrib import admin

from loantypes.models import LoanType


class LoanTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "description")


admin.site.register(LoanType, LoanTypeAdmin)
