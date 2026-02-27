from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from datetime import datetime

from finances.models import GLAccount, JournalEntry

class FinancialReportBase(APIView):
    def get_account_balance(self, account, balance_data_qs, is_debit_normal):
        # 1. Calculate this account's direct balance
        agg = balance_data_qs.filter(gl_account=account).aggregate(
            total_debit=Coalesce(Sum('debit'), Decimal('0')),
            total_credit=Coalesce(Sum('credit'), Decimal('0'))
        )
        if is_debit_normal:
            balance = agg['total_debit'] - agg['total_credit']
        else:
            balance = agg['total_credit'] - agg['total_debit']
            
        # 2. Recursively calculate children
        children = []
        for child in account.sub_accounts.all():
            child_tree = self.get_account_balance(child, balance_data_qs, is_debit_normal)
            if child_tree['balance'] != 0 or child_tree['children']:
                children.append(child_tree)
                balance += Decimal(str(child_tree['balance']))
                
        return {
            'code': account.code,
            'name': account.name,
            'balance': float(balance),
            'children': children
        }

    def build_report_tree(self, account_type, balance_data_qs, is_debit_normal):
        roots = GLAccount.objects.filter(account_type=account_type, parent__isnull=True)
        items = []
        total = Decimal('0')
        
        for root in roots:
            tree = self.get_account_balance(root, balance_data_qs, is_debit_normal)
            if tree['balance'] != 0 or tree['children']:
                items.append(tree)
                total += Decimal(str(tree['balance']))
                
        return items, float(total)

class BalanceSheetView(FinancialReportBase):
    """
    Returns the SACCO Balance Sheet aggregating Assets, Liabilities, and Equity hierarchically.
    """
    def get(self, request):
        as_of_date = request.query_params.get('date', datetime.now().date())
        qs = JournalEntry.objects.filter(transaction_date__lte=as_of_date)
        
        assets, total_assets = self.build_report_tree('Asset', qs, is_debit_normal=True)
        liabilities, total_liabilities = self.build_report_tree('Liability', qs, is_debit_normal=False)
        equity, total_equity = self.build_report_tree('Equity', qs, is_debit_normal=False)

        return Response({
            'as_of_date': as_of_date,
            'assets': {
                'items': assets,
                'total': total_assets
            },
            'liabilities': {
                'items': liabilities,
                'total': total_liabilities
            },
            'equity': {
                'items': equity,
                'total': total_equity
            },
            'total_liabilities_and_equity': total_liabilities + total_equity,
            'in_balance': round(total_assets, 2) == round(total_liabilities + total_equity, 2)
        })

class IncomeStatementView(FinancialReportBase):
    """
    Returns the SACCO Income Statement (Profit & Loss) hierarchically.
    """
    def get(self, request):
        start_date = request.query_params.get('start_date', '2000-01-01')
        end_date = request.query_params.get('end_date', datetime.now().date())
        
        qs = JournalEntry.objects.filter(transaction_date__range=[start_date, end_date])
        
        revenue, total_revenue = self.build_report_tree('Revenue', qs, is_debit_normal=False)
        expenses, total_expenses = self.build_report_tree('Expense', qs, is_debit_normal=True)

        return Response({
            'period': {
                'start': start_date,
                'end': end_date
            },
            'revenue': {
                'items': revenue,
                'total': total_revenue
            },
            'expenses': {
                'items': expenses,
                'total': total_expenses
            },
            'net_income': total_revenue - total_expenses
        })

class TrialBalanceView(APIView):
    """
    Returns the SACCO flat Trial Balance for all accounts.
    """
    def get(self, request):
        as_of_date = request.query_params.get('date', datetime.now().date())
        
        accounts = GLAccount.objects.all()
        results = []
        total_debits = Decimal('0')
        total_credits = Decimal('0')
        
        for acc in accounts:
            totals = JournalEntry.objects.filter(
                gl_account=acc,
                transaction_date__lte=as_of_date
            ).aggregate(
                debit=Coalesce(Sum('debit'), Decimal('0')),
                credit=Coalesce(Sum('credit'), Decimal('0'))
            )
            
            if totals['debit'] != 0 or totals['credit'] != 0:
                results.append({
                    'code': acc.code,
                    'name': acc.name,
                    'type': acc.account_type,
                    'debit': float(totals['debit']),
                    'credit': float(totals['credit'])
                })
                total_debits += totals['debit']
                total_credits += totals['credit']
                
        return Response({
            'date': as_of_date,
            'accounts': results,
            'total_debit': float(total_debits),
            'total_credit': float(total_credits),
            'is_balanced': round(total_debits, 2) == round(total_credits, 2)
        })
