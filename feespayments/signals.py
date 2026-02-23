from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from feespayments.models import FeePayment
from finances.models import GLAccount, JournalEntry
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=FeePayment)
def post_fee_payment_to_gl(sender, instance, created, **kwargs):
    """
    Automatically post balanced Journal Entries to the GL when a FeePayment is recorded.
    DR 1010 - Bank/Cash
    CR 4020 - Membership Fees (Revenue)
    """
    if instance.created_at is None: # Should not happen with TimeStampedModel
        return

    from finances.utils import post_to_gl
    from finances.models import JournalEntry

    with transaction.atomic():
        # 1. Update MemberFee status if fully paid
        member_fee = instance.member_fee
        total_paid = sum(p.amount for p in member_fee.payments.all())
        if total_paid >= member_fee.amount:
            member_fee.is_paid = True
            member_fee.save()

        # 2. Check if already posted to avoid duplicates
        if JournalEntry.objects.filter(reference_id=str(instance.id), source_model="FeePayment").exists():
            return

        # 3. Post to GL using utility
        post_to_gl(instance, 'fee_payment')
