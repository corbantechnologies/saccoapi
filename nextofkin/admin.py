from django.contrib import admin

from nextofkin.models import NextOfKin


class NextOfKinAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "first_name",
        "last_name",
        "relationship",
        "phone",
        "email",
        "address",
    )
    list_filter = ("member",)


admin.site.register(NextOfKin)
