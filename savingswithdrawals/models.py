from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import transaction
from datetime import date

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from savings.models import SavingsAccount

User = get_user_model()


class SavingsWithdrawal(TimeStampedModel, UniversalIdModel, ReferenceModel):
    PAYMENT_METHODS = [
        ("Mpesa", "Mpesa"),
        ("Bank Transfer", "Bank Transfer"),
        ("Cash", "Cash"),
        ("Cheque", "Cheque"),
    ]
    TRANSACTION_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Processing", "Processing"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]

    savings_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        related_name="withdrawals",
    )
    withdrawn_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="savings_withdrawals",
    )
    amount = models.DecimalField(
        decimal_places=2, max_digits=12, validators=[MinValueValidator(0.01)]
    )
    payment_method = models.CharField(choices=PAYMENT_METHODS, max_length=100)
    transaction_status = models.CharField(
        choices=TRANSACTION_STATUS_CHOICES, default="Processing", max_length=100
    )
    receipt_number = models.CharField(blank=True, max_length=50, null=True)
    identity = models.CharField(blank=True, max_length=100, null=True, unique=True)
    # TODO: Add a field for the admin to enter the reason for the withdrawal status i.e approved or rejected

    class Meta:
        verbose_name = "Savings Withdrawal"
        verbose_name_plural = "Savings Withdrawals"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["savings_account", "created_at"]),
            models.Index(fields=["withdrawn_by", "created_at"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"Withdrawal of {self.amount} from {self.savings_account}"

    def generate_identity(self):
        prefix = "WDR"
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        with transaction.atomic():
            # Prevent race conditions
            withdrawals_today = SavingsWithdrawal.objects.filter(
                identity__startswith=f"{prefix}{date_str}"
            ).count()
            sequence = withdrawals_today + 1
            self.identity = f"{prefix}{date_str}{sequence:04d}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.identity:
                self.generate_identity()
            if (
                self.transaction_status == "Completed"
                or self.transaction_status == "Approved"
            ):
                # Update the savings account balance
                self.savings_account.balance -= self.amount
                self.savings_account.save()

        return super().save(*args, **kwargs)
