from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from feetypes.models import FeeType
from memberfees.utils import generate_fee_account_number

User = get_user_model()

class MemberFee(TimeStampedModel, UniversalIdModel, ReferenceModel):
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fees")
    fee_type = models.ForeignKey(FeeType, on_delete=models.CASCADE, related_name="fees")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    account_number = models.CharField(max_length=20, unique=True, default=generate_fee_account_number)
    is_active = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Member Fee"
        verbose_name_plural = "Member Fees"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account_number} - {self.member.member_no} - {self.fee_type.name}"