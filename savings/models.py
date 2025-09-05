from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from savingstypes.models import SavingsType
from savings.utils import generate_account_number

User = get_user_model()


class SavingsAccount(TimeStampedModel, UniversalIdModel, ReferenceModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="savings_accounts"
    )
    account_type = models.ForeignKey(
        SavingsType, on_delete=models.PROTECT, related_name="savings_accounts"
    )
    account_number = models.CharField(
        max_length=20, unique=True, default=generate_account_number
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Savings Account"
        verbose_name_plural = "Savings Accounts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account_number} - {self.user.get_full_name()}"
