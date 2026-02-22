from django.core.management.base import BaseCommand
from django.db import transaction
from savingsdeposits.models import SavingsDeposit
from savingswithdrawals.models import SavingsWithdrawal
from loandisbursements.models import LoanDisbursement
from loanrepayments.models import LoanRepayment
from venturedeposits.models import VentureDeposit
from venturepayments.models import VenturePayment
from loanintereststamarind.models import TamarindLoanInterest
from transactions.utils.reporting_service import ReportingService
from finances.models import JournalEntry

class Command(BaseCommand):
    help = 'Sync all existing transactions to the General Ledger (Journal Entries)'

    def handle(self, *args, **options):
        self.stdout.write("Starting GL Sync...")
        
        # Clear existing entries for fresh start (Optional/Dangerous - usually better to filter)
        # For this initial sync, we clear.
        JournalEntry.objects.all().delete()
        self.stdout.write("Existing Journal Entries cleared.")

        # 1. Savings Deposits
        for dep in SavingsDeposit.objects.all():
            ReportingService.post_savings_deposit(dep)
        self.stdout.write(self.style.SUCCESS("Synced Savings Deposits"))

        # 2. Savings Withdrawals
        for wit in SavingsWithdrawal.objects.all():
            ReportingService.post_savings_withdrawals(wit)
        self.stdout.write(self.style.SUCCESS("Synced Savings Withdrawals"))

        # 3. Loan Disbursements
        for disb in LoanDisbursement.objects.filter(transaction_status="Completed"):
            ReportingService.post_loan_disbursement(disb)
        self.stdout.write(self.style.SUCCESS("Synced Loan Disbursements"))

        # 4. Loan Repayments
        for rep in LoanRepayment.objects.filter(transaction_status="Completed"):
            ReportingService.post_loan_repayment(rep)
        self.stdout.write(self.style.SUCCESS("Synced Loan Repayments"))

        # 5. Venture Deposits
        for v_dep in VentureDeposit.objects.all():
            ReportingService.post_venture_deposit(v_dep)
        self.stdout.write(self.style.SUCCESS("Synced Venture Deposits"))

        # 6. Venture Payments
        for v_pay in VenturePayment.objects.all():
            ReportingService.post_venture_payment(v_pay)
        self.stdout.write(self.style.SUCCESS("Synced Venture Payments"))

        # 7. Interest Accruals
        for interest in TamarindLoanInterest.objects.all():
            ReportingService.post_interest_accrual(interest)
        self.stdout.write(self.style.SUCCESS("Synced Interest Accruals"))

        self.stdout.write(self.style.SUCCESS("GL Sync completed successfully!"))
