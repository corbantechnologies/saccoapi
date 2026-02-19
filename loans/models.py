from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loantypes.models import LoanType
from loans.utils import generate_loan_account_number

User = get_user_model()


class LoanAccount(TimeStampedModel, UniversalIdModel, ReferenceModel):
    """
    Concerns:
    Do we need an amount field for the loan model?
    We definitely need logs to track loan
    Outstanding balance should therefore be the principal plus the interest
    """
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name="loans")
    loan_type = models.ForeignKey(
        LoanType, on_delete=models.PROTECT, related_name="loan_accounts"
    )
    account_number = models.CharField(
        max_length=20, unique=True, default=generate_loan_account_number
    )

    # Core financial fields
    outstanding_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    interest_accrued = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    is_active = models.BooleanField(default=True)

    # System fields
    identity = models.CharField(max_length=100, blank=True, null=True, unique=True)
    last_interest_calculation = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Loan Account"
        verbose_name_plural = "Loan Accounts"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.account_number} - {self.member.member_no} - {self.loan_type.name}"
        )

    def save(self, *args, **kwargs):
        if not self.identity:
            self.identity = slugify(f"{self.member.member_no}-{self.account_number}")
        super().save(*args, **kwargs)
