# loanapplications/utils.py
from decimal import Decimal
from django.db import models
from savings.models import SavingsAccount
from loans.models import LoanAccount
from loanapplications.models import LoanApplication
from guaranteerequests.models import GuaranteeRequest


def compute_loan_coverage(application: LoanApplication) -> dict:
    total_savings = Decimal(
        SavingsAccount.objects.filter(member=application.member).aggregate(
            t=models.Sum("balance")
        )["t"]
        or "0"
    )

    # Committed self-guarantee from OTHER applications
    committed_self_other = Decimal(
        GuaranteeRequest.objects.filter(
            guarantor__member=application.member,
            status="Accepted",
            loan_application__status__in=["Submitted", "Approved", "Disbursed"],
        )
        .exclude(loan_application=application)
        .aggregate(t=models.Sum("guaranteed_amount"))["t"]
        or "0"
    )

    # THIS application's self-guarantee
    self_guarantee_this = Decimal(str(application.self_guaranteed_amount or 0))

    # Available = total savings - committed by others
    available_self = max(Decimal("0"), total_savings - committed_self_other)

    # External guarantees
    total_guaranteed_by_others = Decimal(
        application.guarantors.filter(status="Accepted").aggregate(
            t=models.Sum("guaranteed_amount")
        )["t"]
        or "0"
    )

    # Effective coverage = committed guarantees (self + others)
    effective_coverage = self_guarantee_this + total_guaranteed_by_others

    remaining_to_cover = max(
        Decimal("0"), Decimal(str(application.requested_amount)) - effective_coverage
    )
    is_fully_covered = remaining_to_cover <= Decimal("0")

    return {
        "total_savings": float(total_savings),
        "committed_self_guarantee": float(committed_self_other),
        "available_self_guarantee": float(available_self),
        "total_guaranteed_by_others": float(total_guaranteed_by_others),
        "effective_coverage": float(effective_coverage),
        "remaining_to_cover": float(remaining_to_cover),
        "is_fully_covered": is_fully_covered,
    }
