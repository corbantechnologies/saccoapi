from django.db.models.signals import post_save
from django.dispatch import receiver
from loanintereststamarind.models import TamarindLoanInterest
from finances.utils import post_to_gl

@receiver(post_save, sender=TamarindLoanInterest)
def post_loan_interest_to_gl(sender, instance, created, **kwargs):
    if created:
        post_to_gl(instance, 'loan_interest_accrual')
    else:
        from finances.models import JournalEntry
        if not JournalEntry.objects.filter(reference_id=str(instance.id), source_model="TamarindLoanInterest").exists():
            post_to_gl(instance, 'loan_interest_accrual')
