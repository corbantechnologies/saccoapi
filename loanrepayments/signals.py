from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from decimal import Decimal
import logging

from loanrepayments.models import LoanRepayment
from loanapplications.models import LoanApplication
from guaranteerequests.models import GuaranteeRequest

logger = logging.getLogger(__name__)

@receiver(post_save, sender=LoanRepayment)
def release_guarantee_on_repayment(sender, instance, created, **kwargs):
    """
    Release committed guarantee amount when a loan repayment is made.
    """
    if instance.transaction_status != "Completed":
        return

    # Find the active LoanApplication for this loan account
    # We look for the most recent Disbursed application first
    loan_account = instance.loan_account
    loan_app = LoanApplication.objects.filter(
        loan_account=loan_account,
        status="Disbursed"
    ).order_by('-updated_at').first()

    if not loan_app:
        # Fallback: Check if there's any approved/completed application linked
        loan_app = LoanApplication.objects.filter(
            loan_account=loan_account
        ).order_by('-updated_at').first()
        
    if not loan_app:
        logger.warning(f"No LoanApplication found for repayment {instance.reference} on account {loan_account}")
        return

    original_principal = loan_app.requested_amount
    if original_principal <= 0:
        return

    # Calculate repayment ratio based on the repayment amount vs original principal
    repayment_amount = instance.amount
    ratio = repayment_amount / original_principal
    
    # Fetch all accepted guarantees for this application
    guarantees = GuaranteeRequest.objects.filter(
        loan_application=loan_app,
        status="Accepted"
    )
    
    with transaction.atomic():
        for guarantee in guarantees:
            # Calculate release amount based on the ORIGINAL guaranteed amount
            # This ensures proportional release
            release_amount = guarantee.guaranteed_amount * ratio
            
            # Ensure we don't reduce below zero
            current_balance = guarantee.current_balance if guarantee.current_balance is not None else guarantee.guaranteed_amount
            new_balance = max(Decimal("0.00"), current_balance - release_amount)
            
            # Calculate the actual reduction applied (in case of capping)
            amount_reduced = current_balance - new_balance
            
            if amount_reduced > 0:
                guarantee.current_balance = new_balance
                guarantee.save(update_fields=["current_balance"])
                
                # Update GuarantorProfile committed amount
                profile = guarantee.guarantor
                profile.committed_guarantee_amount = max(
                    Decimal("0.00"), 
                    profile.committed_guarantee_amount - amount_reduced
                )
                profile.save(update_fields=["committed_guarantee_amount"])

