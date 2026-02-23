from django.core.management.base import BaseCommand
from finances.models import GLAccount

class Command(BaseCommand):
    help = 'Bootstrap the initial Chart of Accounts for the SACCO'

    def handle(self, *args, **options):
        accounts = [
            # ASSETS
            {'code': '1010', 'name': 'Cash at Bank', 'account_type': 'Asset'},
            {'code': '1020', 'name': 'Loans Receivable', 'account_type': 'Asset'},
            {'code': '1030', 'name': 'Interest Receivable', 'account_type': 'Asset'},
            
            # LIABILITIES
            {'code': '2010', 'name': 'Member Savings Deposits', 'account_type': 'Liability'},
            {'code': '2020', 'name': 'Member Venture Deposits', 'account_type': 'Liability'},
            
            # EQUITY
            {'code': '3010', 'name': 'Retained Earnings', 'account_type': 'Equity'},
            {'code': '3020', 'name': 'Share Capital', 'account_type': 'Equity'},
            
            # REVENUE
            {'code': '4010', 'name': 'Interest Income', 'account_type': 'Revenue'},
            {'code': '4020', 'name': 'Membership Fees', 'account_type': 'Revenue'},
            
            # EXPENSES
            {'code': '5010', 'name': 'Operating Expenses', 'account_type': 'Expense'},
            {'code': '5020', 'name': 'Bank Charges', 'account_type': 'Expense'},
        ]

        for acc_data in accounts:
            obj, created = GLAccount.objects.get_or_create(
                code=acc_data['code'],
                defaults={'name': acc_data['name'], 'account_type': acc_data['account_type']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created account: {obj}"))
            else:
                self.stdout.write(self.style.WARNING(f"Account already exists: {obj}"))

        self.stdout.write(self.style.SUCCESS('Successfully bootstrapped Chart of Accounts'))
