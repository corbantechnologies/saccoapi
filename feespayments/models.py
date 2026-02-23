from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import transaction
from datetime import date

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from memberfees.models import MemberFee

User = get_user_model()

class FeePayment(TimeStampedModel, UniversalIdModel, ReferenceModel):
    """
    Only record when payment is completed
    """
    PAYMENT_METHOD_CHOICES = [
        ("Mpesa", "Mpesa"),
        ("Bank Transfer", "Bank Transfer"),
        ("Cash", "Cash"),
        ("Mobile Banking", "Mobile Banking"),
    ]
    member_fee = models.ForeignKey(MemberFee, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHOD_CHOICES, default="Cash")
    receipt_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    paid_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="fee_payments",
        null=True,
        blank=True,
    )


    class Meta:
        verbose_name = "Fee Payment"
        verbose_name_plural = "Fee Payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member_fee.member.member_no} - {self.amount}"