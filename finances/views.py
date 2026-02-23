from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from datetime import datetime

from finances.models import GLAccount, JournalEntry

class BalanceSheetView(APIView):
    """
    Returns the SACCO Balance Sheet aggregating Assets, Liabilities, and Equity.
    Equation: Assets = Liabilities + Equity
    """
    def get(self, request):
        as_of_date = request.query_params.get('date', datetime.now().date())
        
        # Helper to get balances
        def get_type_balances(account_type):
            accounts = GLAccount.objects.filter(account_type=account_type)
            data = []
            total = Decimal('0')
            
            for acc in accounts:
                balance_data = JournalEntry.objects.filter(
                    gl_account=acc,
                    transaction_date__lte=as_of_date
                ).aggregate(
                    total_debit=Coalesce(Sum('debit'), Decimal('0')),
                    total_credit=Coalesce(Sum('credit'), Decimal('0'))
                )
                
                # Assets: Debit - Credit
                # Liab/Equity: Credit - Debit
                if account_type == 'Asset':
                    balance = balance_data['total_debit'] - balance_data['total_credit']
                else:
                    balance = balance_data['total_credit'] - balance_data['total_debit']
                
                if balance != 0:
                    data.append({
                        'code': acc.code,
                        'name': acc.name,
                        'balance': float(balance)
                    })
                    total += balance
            
            return data, total

        assets, total_assets = get_type_balances('Asset')
        liabilities, total_liabilities = get_type_balances('Liability')
        equity, total_equity = get_type_balances('Equity')

        return Response({
            'as_of_date': as_of_date,
            'assets': {
                'items': assets,
                'total': float(total_assets)
            },
            'liabilities': {
                'items': liabilities,
                'total': float(total_liabilities)
            },
            'equity': {
                'items': equity,
                'total': float(total_equity)
            },
            'total_liabilities_and_equity': float(total_liabilities + total_equity),
            'in_balance': total_assets == (total_liabilities + total_equity)
        })

class IncomeStatementView(APIView):
    """
    Returns the SACCO Income Statement (Profit & Loss).
    Equation: Net Income = Revenue - Expenses
    """
    def get(self, request):
        start_date = request.query_params.get('start_date', '2000-01-01')
        end_date = request.query_params.get('end_date', datetime.now().date())
        
        def get_type_balances(account_type):
            accounts = GLAccount.objects.filter(account_type=account_type)
            data = []
            total = Decimal('0')
            
            for acc in accounts:
                balance_data = JournalEntry.objects.filter(
                    gl_account=acc,
                    transaction_date__range=[start_date, end_date]
                ).aggregate(
                    total_debit=Coalesce(Sum('debit'), Decimal('0')),
                    total_credit=Coalesce(Sum('credit'), Decimal('0'))
                )
                
                # Revenue: Credit - Debit
                # Expense: Debit - Credit
                if account_type == 'Revenue':
                    balance = balance_data['total_credit'] - balance_data['total_debit']
                else:
                    balance = balance_data['total_debit'] - balance_data['total_credit']
                
                if balance != 0:
                    data.append({
                        'code': acc.code,
                        'name': acc.name,
                        'balance': float(balance)
                    })
                    total += balance
            
            return data, total

        revenue, total_revenue = get_type_balances('Revenue')
        expenses, total_expenses = get_type_balances('Expense')

        return Response({
            'period': {
                'start': start_date,
                'end': end_date
            },
            'revenue': {
                'items': revenue,
                'total': float(total_revenue)
            },
            'expenses': {
                'items': expenses,
                'total': float(total_expenses)
            },
            'net_income': float(total_revenue - total_expenses)
        })

class TrialBalanceView(APIView):
    """
    Returns the SACCO Trial Balance for all accounts.
    Total Debits must equal Total Credits.
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
            'is_balanced': total_debits == total_credits
        })
