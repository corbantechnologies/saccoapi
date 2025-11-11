from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import transaction
from datetime import date

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loans.models import LoanAccount


User = get_user_model()


class LoanDisbursement(TimeStampedModel, UniversalIdModel, ReferenceModel):
    TRANSACTION_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
    ]

    DISBURSEMENT_TYPE_CHOICES = [
        ("Principal", "Principal"),
        ("Interest", "Interest"),
        ("Penalty", "Penalty"),
        ("Refill", "Refill"),
    ]

    loan_account = models.ForeignKey(
        LoanAccount, on_delete=models.PROTECT, related_name="loan_disbursements"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01, message="Amount must be greater than 0")],
    )
    currency = models.CharField(max_length=10, default="KES")
    transaction_status = models.CharField(
        max_length=20, choices=TRANSACTION_STATUS_CHOICES, default="Completed"
    )
    disbursed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    disbursement_type = models.CharField(
        max_length=20, choices=DISBURSEMENT_TYPE_CHOICES, default="Principal"
    )
    identity = models.CharField(max_length=100, blank=True, null=True, unique=True)

    class Meta:
        verbose_name = "Loan Disbursement"
        verbose_name_plural = "Loan Disbursements"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.loan_account} {self.disbursement_type} Disbursement"

    def generate_identity(self):
        prefix = "LD"
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        with transaction.atomic():
            # Prevent race conditions
            disbursements_today = LoanDisbursement.objects.filter(
                identity__startswith=f"{prefix}{date_str}"
            ).count()
            sequence = disbursements_today + 1
            self.identity = f"{prefix}{date_str}{sequence:04d}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.identity:
                self.identity = self.generate_identity()
            
            if self.transaction_status == "Completed":
                # Update the loan account balance
                self.loan_account.outstanding_balance += self.amount
                self.loan_account.save()
        return super().save(*args, **kwargs)
