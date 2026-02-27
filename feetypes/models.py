from django.db import models

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel


class FeeType(UniversalIdModel, TimeStampedModel, ReferenceModel):
    """
    - This is for fees that are required
    - Registration fees
    - Contributions: burials, ceremonies etc
    """
    name = models.CharField(max_length=2550, unique=True)
    description = models.TextField(blank=True, null=True)
    standard_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    # For the GL accounts
    is_income = models.BooleanField(default=False)
    is_expense = models.BooleanField(default=False)
    is_liability = models.BooleanField(default=False)
    is_asset = models.BooleanField(default=False)
    is_equity = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Fee Type"
        verbose_name_plural = "Fee Types"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name