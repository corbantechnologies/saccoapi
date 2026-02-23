from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from feetypes.models import FeeType
from memberfees.models import MemberFee
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def auto_create_member_fees(sender, instance, created, **kwargs):
    """
    Automatically create MemberFee records for a new member based on all active FeeTypes.
    """
    if created and instance.is_member:
        fee_types = FeeType.objects.filter(is_active=True)
        created_fees = []
        for fee_type in fee_types:
            if not MemberFee.objects.filter(member=instance, fee_type=fee_type).exists():
                fee = MemberFee.objects.create(
                    member=instance,
                    fee_type=fee_type,
                    amount=fee_type.standard_amount,
                    remaining_balance=fee_type.standard_amount
                )
                created_fees.append(str(fee))
        
        if created_fees:
            logger.info(f"Auto-created {len(created_fees)} MemberFees for {instance.member_no}")
