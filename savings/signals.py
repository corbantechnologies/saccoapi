from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from django.db import models

from savings.models import SavingsAccount
from guarantorprofile.models import GuarantorProfile


@receiver(post_save, sender=SavingsAccount)
def update_guarantor_max_amount(sender, instance, **kwargs):
    try:
        profile = instance.member.guarantor_profile
        if profile.is_eligible:
            total = SavingsAccount.objects.filter(member=instance.member).aggregate(
                total=models.Sum("balance")
            )["total"] or Decimal("0")
            profile.max_guarantee_amount = total
            profile.save(update_fields=["max_guarantee_amount"])
    except GuarantorProfile.DoesNotExist:
        pass
