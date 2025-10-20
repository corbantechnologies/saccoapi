from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import transaction
from datetime import date

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from ventures.models import VentureAccount

User = get_user_model()


class VentureDeposit(TimeStampedModel, UniversalIdModel, ReferenceModel):
    venture_account = models.ForeignKey(
        VentureAccount, on_delete=models.PROTECT, related_name="deposits"
    )
    deposited_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="venture_deposits",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    identity = models.CharField(max_length=200, unique=True, blank=True, null=True)

    class Meta:
        verbose_name = "Venture Deposit"
        verbose_name_plural = "Venture Deposits"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["venture_account", "created_at"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"Deposit {self.reference} - {self.amount} to {self.venture_account}"

    def generate_identity(self):
        prefix = "VD"
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        with transaction.atomic():
            # Prevent race conditions
            deposits_today = VentureDeposit.objects.filter(
                identity__startswith=f"{prefix}{date_str}"
            ).count()
            sequence = deposits_today + 1
            self.identity = f"{prefix}{date_str}{sequence:04d}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.identity:
                self.identity = self.generate_identity()

            # Update the venture account balance
            self.venture_account.balance += self.amount
            self.venture_account.save()

        return super().save(*args, **kwargs)
