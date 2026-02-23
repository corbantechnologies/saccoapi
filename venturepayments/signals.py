from django.db.models.signals import post_save
from django.dispatch import receiver
from venturepayments.models import VenturePayment
from finances.utils import post_to_gl

@receiver(post_save, sender=VenturePayment)
def post_venture_payment_to_gl(sender, instance, created, **kwargs):
    if created and instance.transaction_status == "Completed":
        post_to_gl(instance, 'venture_payment')
    elif not created and instance.transaction_status == "Completed":
        from finances.models import JournalEntry
        if not JournalEntry.objects.filter(reference_id=str(instance.id), source_model="VenturePayment").exists():
            post_to_gl(instance, 'venture_payment')
