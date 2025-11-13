from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from django.db import models

from loans.models import LoanAccount
from guarantorprofile.models import GuarantorProfile

@receiver(post_save, sender=LoanAccount)
def update_guarantor_max_amount(sender, instance, **kwargs):
    pass