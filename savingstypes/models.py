from django.db import models

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel


class SavingsType(UniversalIdModel, TimeStampedModel, ReferenceModel):
    name = models.CharField(max_length=2550, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Savings Type"
        verbose_name_plural = "Savings Types"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
