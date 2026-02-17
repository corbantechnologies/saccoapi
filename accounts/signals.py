from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from guarantorprofile.models import GuarantorProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_guarantor_profile(sender, instance, created, **kwargs):
    if created:
        GuarantorProfile.objects.create(member=instance, is_eligible=True)