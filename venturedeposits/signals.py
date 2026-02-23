from django.db.models.signals import post_save
from django.dispatch import receiver
from venturedeposits.models import VentureDeposit
from finances.utils import post_to_gl

@receiver(post_save, sender=VentureDeposit)
def post_venture_deposit_to_gl(sender, instance, created, **kwargs):
    if created:
        post_to_gl(instance, 'venture_deposit')
    else:
        # For VentureDeposit, we post on creation and don't typically have a status field like SavingsDeposit
        # If one is added later, we can add a check here.
        pass
