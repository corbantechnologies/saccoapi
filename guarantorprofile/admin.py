from django.contrib import admin

from guarantorprofile.models import GuarantorProfile


class GuarantorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "is_eligible",
        "max_active_guarantees",
        "max_guarantee_amount",
        "committed_guarantee_amount",
    )

    search_fields = ("member__first_name", "member__last_name")


admin.site.register(GuarantorProfile, GuarantorProfileAdmin)
