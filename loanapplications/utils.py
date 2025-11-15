from decimal import Decimal
from django.db import models
from savings.models import SavingsAccount
from loanapplications.models import LoanApplication


def compute_loan_coverage(application):
    """
    Returns accurate coverage using:
    - Available self-guarantee (savings - committed from active loans)
    - Accepted external guarantees
    """
    pass
