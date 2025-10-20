from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from venturetypes.models import VentureType
from ventures.utils import generate_venture_account_number

User = get_user_model()


class VentureAccount(TimeStampedModel, UniversalIdModel, ReferenceModel):
    member = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="venture_accounts"
    )
    venture_type = models.ForeignKey(
        VentureType, on_delete=models.PROTECT, related_name="venture_accounts"
    )
    account_number = models.CharField(
        max_length=20, unique=True, default=generate_venture_account_number
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    identity = models.CharField(max_length=100, blank=True, null=True, unique=True)

    class Meta:
        verbose_name = "Venture Account"
        verbose_name_plural = "Venture Accounts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account_number} - {self.member.member_no}"

    def save(self, *args, **kwargs):
        if not self.identity:
            self.identity = slugify(f"{self.member.member_no}-{self.account_number}")
        super().save(*args, **kwargs)
