from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from datetime import datetime
from dateutil.relativedelta import relativedelta

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loantypes.models import LoanType
from loans.utils import generate_loan_account_number

User = get_user_model()


class LoanAccount(TimeStampedModel, UniversalIdModel, ReferenceModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="loans")
    loan_type = models.ForeignKey(
        LoanType, on_delete=models.PROTECT, related_name="loan_accounts"
    )
    account_number = models.CharField(
        max_length=20, unique=True, default=generate_loan_account_number
    )
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    outstanding_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    interest_accrued = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    is_active = models.BooleanField(default=True)

    # TODO: Implement approval workflow
    is_approved = models.BooleanField(default=False)
    approval_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_loans",
    )
    identity = models.CharField(max_length=100, blank=True, null=True, unique=True)
    last_interest_calculation = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Loan Account"
        verbose_name_plural = "Loan Accounts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account_number}"

    def calculate_monthly_interest(self):
        """
        Calculate monthly compound interest based on loan type's interest rate.
        """
        if not self.is_active:
            return

        now = datetime.now()
        if not self.last_interest_calculation:
            self.last_interest_calculation = self.created_at

        months_passed = relativedelta(now, self.last_interest_calculation).months
        if months_passed >= 1:
            monthly_rate = self.loan_type.interest_rate / 12 / 100
            monthly_interest = (
                self.outstanding_balance + self.interest_accrued
            ) * monthly_rate
            self.interest_accrued += monthly_interest
            self.last_interest_calculation = now
            self.save()

    def save(self, *args, **kwargs):
        if not self.identity:
            self.identity = slugify(f"{self.user.member_no}-{self.account_number}")
        if self.is_approved and not self.approval_date:
            self.approval_date = datetime.now()
            if not self.outstanding_balance:
                self.outstanding_balance = self.loan_amount
        if self.outstanding_balance <= 0:
            self.is_active = False
        super().save(*args, **kwargs)
