from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import UniversalIdModel, TimeStampedModel, ReferenceModel

User = get_user_model()


class NextOfKin(UniversalIdModel, TimeStampedModel, ReferenceModel):
    member = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="next_of_kin"
    )
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=255)
    phone = models.CharField(max_length=25)
    percentage = models.DecimalField(max_digits=12, decimal_places=2)
    email = models.EmailField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Next of Kin"
        verbose_name_plural = "Next of Kins"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
