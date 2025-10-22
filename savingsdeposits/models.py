from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import transaction
from datetime import date

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from savings.models import SavingsAccount

User = get_user_model()


class SavingsDeposit(TimeStampedModel, UniversalIdModel, ReferenceModel):
    PAYMENT_METHOD_CHOICES = [
        ("Mpesa", "Mpesa"),
        ("Bank Transfer", "Bank Transfer"),
        ("Cash", "Cash"),
        ("Cheque", "Cheque"),
        ("Mobile Banking", "Mobile Banking"),
        ("Standing Order", "Standing Order"),
    ]
    DEPOSIT_TYPE_CHOICES = [
        ("Opening Balance", "Opening Balance"),
        ("Payroll Deduction", "Payroll Deduction"),
        ("Individual Deposit", "Individual Deposit"),
        ("Dividend Deposit", "Dividend Deposit"),
        ("Other", "Other"),
    ]
    TRANSACTION_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
    ]

    savings_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        related_name="deposits",
    )
    deposited_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="savings_deposits",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01, message="Amount must be greater than 0")],
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    currency = models.CharField(max_length=10, default="KES")
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHOD_CHOICES, default="Cash")
    deposit_type = models.CharField(
        max_length=100, choices=DEPOSIT_TYPE_CHOICES, default="Individual Deposit"
    )
    transaction_status = models.CharField(
        max_length=20, choices=TRANSACTION_STATUS_CHOICES, blank=True, null=True
    )
    is_active = models.BooleanField(default=True)
    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    identity = models.CharField(max_length=100, blank=True, null=True, unique=True)

    # Mpesa fields: to be added later

    class Meta:
        verbose_name = "Savings Deposit"
        verbose_name_plural = "Savings Deposits"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["savings_account", "created_at"]),
            models.Index(fields=["deposited_by", "created_at"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"Deposit {self.reference} - {self.amount} to {self.savings_account}"

    def generate_identity(self):
        prefix = "DEP"
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        with transaction.atomic():
            # Prevent race conditions
            deposits_today = SavingsDeposit.objects.filter(
                identity__startswith=f"{prefix}{date_str}"
            ).count()
            sequence = deposits_today + 1
            self.identity = f"{prefix}{date_str}{sequence:04d}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.identity:
                self.identity = self.generate_identity()
            if self.is_active and self.transaction_status == "Completed":
                # Update the savings account balance
                self.savings_account.balance += self.amount
                self.savings_account.save()

        return super().save(*args, **kwargs)
