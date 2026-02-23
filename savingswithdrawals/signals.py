from django.db.models.signals import post_save
from django.dispatch import receiver
from savingswithdrawals.models import SavingsWithdrawal
from finances.utils import post_to_gl

@receiver(post_save, sender=SavingsWithdrawal)
def post_savings_withdrawal_to_gl(sender, instance, created, **kwargs):
    if created and instance.transaction_status == "Completed":
        post_to_gl(instance, 'savings_withdrawal')
    elif not created and instance.transaction_status == "Completed":
        from finances.models import JournalEntry
        if not JournalEntry.objects.filter(reference_id=str(instance.id), source_model="SavingsWithdrawal").exists():
            post_to_gl(instance, 'savings_withdrawal')
