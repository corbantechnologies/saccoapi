from django.urls import path
from finances.views import BalanceSheetView, IncomeStatementView, TrialBalanceView

urlpatterns = [
    path('balance-sheet/', BalanceSheetView.as_view(), name='balance-sheet'),
    path('income-statement/', IncomeStatementView.as_view(), name='income-statement'),
    path('trial-balance/', TrialBalanceView.as_view(), name='trial-balance'),
]
