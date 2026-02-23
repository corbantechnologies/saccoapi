from django.db.models.signals import post_save
from django.dispatch import receiver
from savingsdeposits.models import SavingsDeposit
from finances.utils import post_to_gl

@receiver(post_save, sender=SavingsDeposit)
def post_savings_deposit_to_gl(sender, instance, created, **kwargs):
    if created and instance.transaction_status == "Completed":
        post_to_gl(instance, 'savings_deposit')
    elif not created and instance.transaction_status == "Completed":
        # Check if already posted to avoid duplicates
        from finances.models import JournalEntry
        if not JournalEntry.objects.filter(reference_id=str(instance.id), source_model="SavingsDeposit").exists():
            post_to_gl(instance, 'savings_deposit')
