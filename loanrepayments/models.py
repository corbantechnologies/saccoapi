from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from datetime import date
from django.db import transaction

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loans.models import LoanAccount

User = get_user_model()


class LoanRepayment(TimeStampedModel, UniversalIdModel, ReferenceModel):
    PAYMENT_METHOD_CHOICES = [
        ("Mpesa", "Mpesa"),
        ("Bank Transfer", "Bank Transfer"),
        ("Cash", "Cash"),
        ("Cheque", "Cheque"),
        ("Mobile Banking", "Mobile Banking"),
        ("Standing Order", "Standing Order"),
    ]

    REPAYMENT_TYPE_CHOICES = [
        ("Regular Repayment", "Regular Repayment"),
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

    loan_account = models.ForeignKey(
        LoanAccount,
        on_delete=models.PROTECT,
        related_name="repayments",
    )
    paid_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="loan_repayments",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01, message="Amount must be greater than 0")],
    )
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHOD_CHOICES, default="Cash")
    repayment_type = models.CharField(
        max_length=100, choices=REPAYMENT_TYPE_CHOICES, default="Regular Repayment"
    )
    transaction_status = models.CharField(
        max_length=100, choices=TRANSACTION_STATUS_CHOICES, default="Pending"
    )
    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    identity = models.CharField(max_length=100, blank=True, null=True, unique=True)

    class Meta:
        verbose_name = "Loan Repayment"
        verbose_name_plural = "Loan Repayments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["loan_account", "created_at"]),
            models.Index(fields=["paid_by", "created_at"]),
            models.Index(fields=["transaction_status"]),
        ]

    def __str__(self):
        return f"Repayment {self.reference} for Loan {self.loan_account.account_number} - Amount: {self.amount}"

    def generate_identity(self):
        prefix = "LR"
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        with transaction.atomic():
            repayments_today = LoanRepayment.objects.filter(
                identity__startswith=f"{prefix}{date_str}"
            ).count()
            sequence = repayments_today + 1
            self.identity = f"{prefix}{date_str}{sequence:04d}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.identity:
                self.generate_identity()

            if self.transaction_status == "Completed":
                if self.repayment_type == "Interest Payment":
                    self.loan_account.interest_accrued -= self.amount
                    if self.loan_account.interest_accrued < 0:
                        self.loan_account.interest_accrued = 0
                else:
                    self.loan_account.outstanding_balance -= self.amount
                    if self.loan_account.outstanding_balance <= 0:
                        self.loan_account.outstanding_balance = 0
                        self.loan_account.is_active = False
                self.loan_account.save()

            super().save(*args, **kwargs)
