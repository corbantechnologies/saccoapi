from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loanapplications.models import LoanApplication
from guarantorprofile.models import GuarantorProfile

User = get_user_model()


class GuaranteeRequest(TimeStampedModel, UniversalIdModel, ReferenceModel):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("Declined", "Declined"),
        ("Cancelled", "Cancelled"),
    ]

    member = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="guarantor_requests"
    )
    loan_application = models.ForeignKey(
        LoanApplication, on_delete=models.CASCADE, related_name="guarantors"
    )
    guarantor = models.ForeignKey(
        GuarantorProfile, on_delete=models.CASCADE, related_name="guarantees"
    )
    guaranteed_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="Pending")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Guarantee Request"
        verbose_name_plural = "Guarantee Requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member.member_no} - {self.guaranteed_amount}"
