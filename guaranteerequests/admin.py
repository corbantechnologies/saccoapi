from django.contrib import admin

from guaranteerequests.models import GuaranteeRequest


class GuaranteeRequestAdmin(admin.ModelAdmin):
    list_display = (
        "loan_application",
        "guarantor",
        "status",
    )


admin.site.register(GuaranteeRequest, GuaranteeRequestAdmin)
