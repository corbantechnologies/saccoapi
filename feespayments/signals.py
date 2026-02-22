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
    if created:
        try:
            with transaction.atomic():
                # 1. Get GL Accounts
                bank_account = GLAccount.objects.get(code='1010')
                fee_income_account = GLAccount.objects.get(code='4020')
                
                # 2. Update MemberFee status if fully paid
                # Note: For now assuming one payment satisfies the fee, 
                # or we can check total payments vs fee amount.
                member_fee = instance.member_fee
                total_paid = sum(p.amount for p in member_fee.payments.all())
                if total_paid >= member_fee.amount:
                    member_fee.is_paid = True
                    member_fee.save()

                # 3. Create Journal Entries
                description = f"Fee Payment: {member_fee.fee_type.name} - {member_fee.member.member_no}"
                
                # Debit Bank
                JournalEntry.objects.create(
                    transaction_date=instance.created_at.date(),
                    description=description,
                    gl_account=bank_account,
                    debit=instance.amount,
                    credit=0,
                    reference_id=str(instance.id),
                    source_model="FeePayment",
                    posted_by=instance.paid_by
                )
                
                # Credit Revenue
                JournalEntry.objects.create(
                    transaction_date=instance.created_at.date(),
                    description=description,
                    gl_account=fee_income_account,
                    debit=0,
                    credit=instance.amount,
                    reference_id=str(instance.id),
                    source_model="FeePayment",
                    posted_by=instance.paid_by
                )
                
                logger.info(f"GL Posted for FeePayment {instance.reference}: DR 1010 / CR 4020")
                
        except GLAccount.DoesNotExist as e:
            logger.error(f"Failed to post to GL: Required account (1010 or 4020) not found.")
        except Exception as e:
            logger.error(f"Error posting FeePayment to GL: {str(e)}")
