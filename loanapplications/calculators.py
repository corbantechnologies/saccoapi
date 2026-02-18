# calculators.py
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Literal

# ----------------------------------------------------------------------
# Helper: date stepping
# ----------------------------------------------------------------------
DELTA = {
    "daily": relativedelta(days=1),
    "weekly": relativedelta(weeks=1),
    "biweekly": relativedelta(weeks=2),
    "monthly": relativedelta(months=1),
    "quarterly": relativedelta(months=3),
    "annually": relativedelta(years=1),
}
MONTHS_PER = {
    "daily": Decimal("1") / 30,
    "weekly": Decimal("1") / 4,
    "biweekly": Decimal("0.5"),
    "monthly": Decimal("1"),
    "quarterly": Decimal("3"),
    "annually": Decimal("12"),
}


# ----------------------------------------------------------------------
# Reducing Balance – Fixed Term → monthly payment
# ----------------------------------------------------------------------
def reducing_fixed_term(
    principal: Decimal,
    annual_rate: Decimal,
    term_months: int,
    start_date: date,
    repayment_frequency: str = "monthly",
) -> Dict:
    if term_months <= 0:
        raise ValueError("term_months must be > 0")

    monthly_rate = (annual_rate / 100) / 12
    n = Decimal(term_months)

    if monthly_rate == 0:
        pmt = principal / n
    else:
        pmt = (
            principal
            * (monthly_rate * (1 + monthly_rate) ** n)
            / ((1 + monthly_rate) ** n - 1)
        )
    pmt = pmt.quantize(Decimal("0.01"), ROUND_HALF_UP)

    return _build_schedule(
        principal, monthly_rate, pmt, term_months, start_date, repayment_frequency
    )


# ----------------------------------------------------------------------
# Reducing Balance – Fixed Payment → term
# ----------------------------------------------------------------------
def reducing_fixed_payment(
    principal: Decimal,
    annual_rate: Decimal,
    payment_per_month: Decimal,
    start_date: date,
    repayment_frequency: str = "monthly",
    max_months: int = 360,
) -> Dict:
    if payment_per_month <= 0:
        raise ValueError("payment_per_month must be > 0")

    monthly_rate = (annual_rate / 100) / 12
    balance = principal
    total_interest = Decimal("0")
    schedule: List[dict] = []
    cur = start_date + DELTA[repayment_frequency]
    months = 0

    while balance > Decimal("0.01") and months < max_months:
        interest = (balance * monthly_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
        principal_due = (payment_per_month - interest).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )

        if principal_due > balance:
            principal_due = balance
            total_due = principal_due + interest
        else:
            total_due = payment_per_month

        balance = (balance - principal_due).quantize(Decimal("0.01"), ROUND_HALF_UP)
        total_interest += interest

        schedule.append(
            {
                "due_date": cur.isoformat(),
                "principal_due": float(principal_due),
                "interest_due": float(interest),
                "total_due": float(total_due),
                "balance_after": float(balance),
            }
        )

        cur += DELTA[repayment_frequency]
        months += 1

    return {
        "term_months": months,
        "monthly_payment": float(payment_per_month),
        "total_interest": float(total_interest.quantize(Decimal("0.01"))),
        "total_repayment": float(
            (principal + total_interest).quantize(Decimal("0.01"))
        ),
        "schedule": schedule,
    }


# ----------------------------------------------------------------------
# Shared schedule builder (used by fixed-term)
# ----------------------------------------------------------------------
def _build_schedule(
    principal: Decimal,
    monthly_rate: Decimal,
    pmt: Decimal,
    term_months: int,
    start_date: date,
    freq: str,
) -> Dict:
    balance = principal
    total_interest = Decimal("0")
    schedule: List[dict] = []
    cur = start_date + DELTA[freq]

    for _ in range(term_months):
        interest = (balance * monthly_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
        principal_due = (pmt - interest).quantize(Decimal("0.01"), ROUND_HALF_UP)

        if balance < principal_due:
            principal_due = balance
            total_due = principal_due + interest
        else:
            total_due = pmt

        balance = (balance - principal_due).quantize(Decimal("0.01"), ROUND_HALF_UP)
        total_interest += interest

        schedule.append(
            {
                "due_date": cur.isoformat(),
                "principal_due": float(principal_due),
                "interest_due": float(interest),
                "total_due": float(total_due),
                "balance_after": float(balance),
            }
        )
        cur += DELTA[freq]

    return {
        "term_months": term_months,
        "monthly_payment": float(pmt),
        "total_interest": float(total_interest.quantize(Decimal("0.01"))),
        "total_repayment": float(
            (principal + total_interest).quantize(Decimal("0.01"))
        ),
        "schedule": schedule,
    }
