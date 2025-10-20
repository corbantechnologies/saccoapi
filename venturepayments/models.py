from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from datetime import date
from django.db import transaction

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from ventures.models import VentureAccount

User = get_user_model()


class VenturePayment(TimeStampedModel, UniversalIdModel, ReferenceModel):
    PAYMENT_METHOD_CHOICES = [
        ("Mpesa", "Mpesa"),
        ("Bank Transfer", "Bank Transfer"),
        ("Cash", "Cash"),
        ("Cheque", "Cheque"),
        ("Mobile Banking", "Mobile Banking"),
        ("Standing Order", "Standing Order"),
    ]

    PAYMENT_TYPE_CHOICES = [
        ("Regular Payment", "Regular Payment"),
        ("Payroll Deduction", "Payroll Deduction"),
        ("Interest Payment", "Interest Payment"),
        ("Individual Settlement", "Individual Settlement"),
        ("Early Settlement", "Early Settlement"),
        ("Partial Payment", "Partial Payment"),
        ("Other", "Other"),
    ]

    TRANSACTION_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
    ]

    venture_account = models.ForeignKey(
        VentureAccount, on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(
        decimal_places=2,
        default=0.0,
        max_digits=12,
        validators=[MinValueValidator(0.01, message="Amount must be greater than 0")],
    )
    paid_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="venture_payments",
        null=True,
        blank=True,
    )
    payment_method = models.CharField(
        choices=PAYMENT_METHOD_CHOICES, max_length=100, default="Cash"
    )
    transaction_status = models.CharField(
        choices=TRANSACTION_STATUS_CHOICES, max_length=100, default="Pending"
    )
    payment_type = models.CharField(
        choices=PAYMENT_TYPE_CHOICES, max_length=100, default="Individual Settlement"
    )
    payment_date = models.DateField(default=date.today)
    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    identity = models.CharField(max_length=100, blank=True, null=True, unique=True)

    class Meta:
        verbose_name = "Venture Payment"
        verbose_name_plural = "Venture Payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.reference} for Venture {self.venture_account.account_number} - Amount: {self.amount}"

    def generate_identity(self):
        prefix = "VP"
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        with transaction.atomic():
            payments_today = VenturePayment.objects.filter(
                identity__startswith=f"{prefix}{date_str}"
            ).count()
            sequence = payments_today + 1
            self.identity = f"{prefix}{date_str}{sequence:04d}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.identity:
                self.identity = self.generate_identity()

            # Update the venture account balance
            self.venture_account.balance -= self.amount
            self.venture_account.save()

        return super().save(*args, **kwargs)
