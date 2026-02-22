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
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Fee Type"
        verbose_name_plural = "Fee Types"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name