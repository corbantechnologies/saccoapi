from django.core.management.base import BaseCommand
from django.db import transaction
from finances.utils import post_to_gl
from finances.models import JournalEntry
from savingsdeposits.models import SavingsDeposit
from savingswithdrawals.models import SavingsWithdrawal
from venturedeposits.models import VentureDeposit
from venturepayments.models import VenturePayment
from loandisbursements.models import LoanDisbursement
from loanrepayments.models import LoanRepayment
from loanintereststamarind.models import TamarindLoanInterest
from feespayments.models import FeePayment

class Command(BaseCommand):
    help = 'Backfill historical transactions into the General Ledger'

    def handle(self, *args, **options):
        self.stdout.write("Starting GL Backfill...")
        
        transaction_models = [
            (SavingsDeposit, 'savings_deposit', 'SavingsDeposit'),
            (SavingsWithdrawal, 'savings_withdrawal', 'SavingsWithdrawal'),
            (VentureDeposit, 'venture_deposit', 'VentureDeposit'),
            (VenturePayment, 'venture_payment', 'VenturePayment'),
            (LoanDisbursement, 'loan_disbursement', 'LoanDisbursement'),
            (LoanRepayment, 'loan_repayment_principal', 'LoanRepayment'), # Default to principal, logic handles interest
            (TamarindLoanInterest, 'loan_interest_accrual', 'TamarindLoanInterest'),
            (FeePayment, 'fee_payment', 'FeePayment'),
        ]
        
        for model_class, gl_type, source_name in transaction_models:
            self.stdout.write(f"Processing {source_name}...")
            count = 0
            
            # Simple filtering for repayments
            if model_class == LoanRepayment:
                queryset = model_class.objects.filter(transaction_status="Completed")
            elif hasattr(model_class, 'transaction_status'):
                queryset = model_class.objects.filter(transaction_status="Completed")
            else:
                queryset = model_class.objects.all()

            for instance in queryset:
                # Check if already posted
                if not JournalEntry.objects.filter(reference_id=str(instance.id), source_model=source_name).exists():
                    
                    specific_gl_type = gl_type
                    if model_class == LoanRepayment and instance.repayment_type == "Interest Payment":
                        specific_gl_type = "loan_repayment_interest"
                        
                    if post_to_gl(instance, specific_gl_type):
                        count += 1
            
            self.stdout.write(self.style.SUCCESS(f"Successfully backfilled {count} entries for {source_name}"))

        self.stdout.write(self.style.SUCCESS("GL Backfill Complete!"))
