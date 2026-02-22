from django.contrib import admin

from feespayments.models import FeePayment

class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ["member_fee", "amount", "payment_method", "paid_by"]
    list_filter = ["member_fee", "amount", "payment_method", "paid_by"]
    search_fields = ["member_fee", "amount", "payment_method", "paid_by"]
    ordering = ["-created_at"]
    

admin.site.register(FeePayment, FeePaymentAdmin)
