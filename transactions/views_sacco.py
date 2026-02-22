from datetime import datetime
from django.db.models import Sum, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from finances.models import GLAccount, JournalEntry
from decimal import Decimal

class SACCOSummaryView(APIView):
    """
    Consolidated financial overview of the entire SACCO.
    """
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date', datetime.now().date().isoformat())
        
        # 1. Fetch all accounts and their net positions
        accounts = GLAccount.objects.filter(is_active=True)
        
        # Helper to get balance for an account
        def get_balance(acc, to_date):
            entries = JournalEntry.objects.filter(gl_account=acc, transaction_date__lte=to_date)
            totals = entries.aggregate(
                dr=Sum('debit'),
                cr=Sum('credit')
            )
            dr = totals['dr'] or Decimal('0')
            cr = totals['cr'] or Decimal('0')
            
            # Normal balance direction logic
            if acc.account_type in ['Asset', 'Expense']:
                return dr - cr
            else:
                return cr - dr

        assets = []
        liabilities = []
        equity = []
        revenue = []
        expenses = []
        
        totals = {
            'assets': Decimal('0'),
            'liabilities': Decimal('0'),
            'equity': Decimal('0'),
            'revenue': Decimal('0'),
            'expenses': Decimal('0'),
        }

        for acc in accounts:
            balance = get_balance(acc, end_date)
            acc_info = {
                'code': acc.code,
                'name': acc.name,
                'balance': float(balance)
            }
            
            if acc.account_type == 'Asset':
                assets.append(acc_info)
                totals['assets'] += balance
            elif acc.account_type == 'Liability':
                liabilities.append(acc_info)
                totals['liabilities'] += balance
            elif acc.account_type == 'Equity':
                equity.append(acc_info)
                totals['equity'] += balance
            elif acc.account_type == 'Revenue':
                revenue.append(acc_info)
                totals['revenue'] += balance
            elif acc.account_type == 'Expense':
                expenses.append(acc_info)
                totals['expenses'] += balance

        net_profit = totals['revenue'] - totals['expenses']
        
        # Prepare final response data
        resp_totals = {k: float(v) for k, v in totals.items()}
        
        return Response({
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'revenue': revenue,
            'expenses': expenses,
            'totals': resp_totals,
            'net_profit': float(net_profit),
            'end_date': end_date
        }, status=status.HTTP_200_OK)

class CashbookView(APIView):
    """
    Chronological flow of funds (Cash/Bank account entries).
    """
    def get(self, request):
        # We focus on the Cash at Bank account (Code 1010)
        cash_acc = GLAccount.objects.get(code='1010')
        entries = JournalEntry.objects.filter(gl_account=cash_acc).order_by('transaction_date', 'created_at')
        
        results = []
        running_balance = Decimal('0')
        
        for entry in entries:
            running_balance += (entry.debit - entry.credit)
            results.append({
                'date': entry.transaction_date,
                'description': entry.description,
                'debit': float(entry.debit),
                'credit': float(entry.credit),
                'balance': float(running_balance),
                'reference': entry.reference_id,
                'source': entry.source_model
            })
            
        return Response(results, status=status.HTTP_200_OK)
