# loanapplications/utils.py
from decimal import Decimal
from django.db import models
from savings.models import SavingsAccount
from loans.models import LoanAccount
from loanapplications.models import LoanApplication


def compute_loan_coverage(application: LoanApplication) -> dict:
    """
    Accurate coverage for a loan application.
    Used in:
    - GuaranteeRequest validation
    - Submit button logic
    - Status auto-update
    """
    # 1. Total savings
    total_savings = SavingsAccount.objects.filter(member=application.member).aggregate(
        t=models.Sum("balance")
    )["t"] or Decimal("0")

    # 2. Self-guarantee already committed in ACTIVE LoanAccounts of this type
    # → Use reverse relation: loan_account__applications__self_guaranteed_amount
    committed_self = LoanAccount.objects.filter(
        member=application.member,
        loan_type=application.product,
        is_active=True,
        applications__self_guaranteed_amount__gt=0,
    ).aggregate(t=models.Sum("applications__self_guaranteed_amount"))["t"] or Decimal(
        "0"
    )

    available_self = max(Decimal("0"), total_savings - committed_self)

    # 3. External guarantees (accepted only)
    total_guaranteed_by_others = application.guarantors.filter(
        status="Accepted"
    ).aggregate(t=models.Sum("guaranteed_amount"))["t"] or Decimal("0")

    effective_coverage = available_self + total_guaranteed_by_others
    remaining_to_cover = max(
        Decimal("0"), application.requested_amount - effective_coverage
    )
    is_fully_covered = remaining_to_cover <= Decimal("0")

    return {
        "total_savings": total_savings,
        "committed_self_guarantee": committed_self,
        "available_self_guarantee": available_self,
        "total_guaranteed_by_others": total_guaranteed_by_others,
        "effective_coverage": effective_coverage,
        "remaining_to_cover": remaining_to_cover,
        "is_fully_covered": is_fully_covered,
    }
