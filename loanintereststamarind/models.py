from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loans.models import LoanAccount

User = get_user_model()

class TamarindLoanInterest(TimeStampedModel, UniversalIdModel, ReferenceModel):
    loan_account = models.ForeignKey(LoanAccount, on_delete=models.CASCADE, related_name="tamarind_interests")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Tamarind Loan Interest"
        verbose_name_plural = "Tamarind Loan Interests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Tamarind Loan Interest for Loan {self.loan_account.account_number} - Amount: {self.amount}"