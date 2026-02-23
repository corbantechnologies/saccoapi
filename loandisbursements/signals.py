from django.db.models.signals import post_save
from django.dispatch import receiver
from loandisbursements.models import LoanDisbursement
from finances.utils import post_to_gl

@receiver(post_save, sender=LoanDisbursement)
def post_loan_disbursement_to_gl(sender, instance, created, **kwargs):
    if created and instance.transaction_status == "Completed":
        post_to_gl(instance, 'loan_disbursement')
    elif not created and instance.transaction_status == "Completed":
        from finances.models import JournalEntry
        if not JournalEntry.objects.filter(reference_id=str(instance.id), source_model="LoanDisbursement").exists():
            post_to_gl(instance, 'loan_disbursement')
