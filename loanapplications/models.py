from django.db import models
from django.contrib.auth import get_user_model
from datetime import date

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loantypes.models import LoanType
from loans.models import LoanAccount


User = get_user_model()


class LoanApplication(UniversalIdModel, TimeStampedModel, ReferenceModel):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Ready for Amendment", "Ready for Amendment"),
        ("Amended", "Amended"),
        ("In Progress", "In Progress"),
        ("Ready for Submission", "Ready for Submission"),
        ("Submitted", "Submitted"),
        ("Approved", "Approved"),
        ("Disbursed", "Disbursed"),
        ("Declined", "Declined"),
        ("Cancelled", "Cancelled"),
    ]

    REPAYMENT_FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("biweekly", "Biweekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annually", "Annually"),
    ]

    CALCULATION_MODE_CHOICES = [
        ("fixed_term", "Fixed Term"),
        ("fixed_payment", "Fixed Payment"),
    ]

    member = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="loan_applications"
    )
    product = models.ForeignKey(
        LoanType, on_delete=models.PROTECT, related_name="applications"
    )
    requested_amount = models.DecimalField(max_digits=15, decimal_places=2)
    repayment_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    total_interest = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    # REDUCING BALANCE FIELDS
    calculation_mode = models.CharField(max_length=20, choices=CALCULATION_MODE_CHOICES)
    term_months = models.PositiveIntegerField(null=True, blank=True)
    monthly_payment = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    repayment_frequency = models.CharField(
        max_length=20, choices=REPAYMENT_FREQUENCY_CHOICES, default="monthly"
    )
    start_date = models.DateField()
    projection_snapshot = models.JSONField(default=dict)
    self_guaranteed_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00
    )
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="Ready for Amendment"
    )
    loan_account = models.ForeignKey(
        LoanAccount,
        on_delete=models.PROTECT,
        related_name="applications",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Loan Application"
        verbose_name_plural = "Loan Applications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member.member_no} - {self.requested_amount}"
