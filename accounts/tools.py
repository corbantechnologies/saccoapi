import logging

from savings.models import SavingsAccount
from savingstypes.models import SavingsType
from venturetypes.models import VentureType
from ventures.models import VentureAccount
from loans.models import LoanAccount
from loantypes.models import LoanType
from feetypes.models import FeeType
from memberfees.models import MemberFee


logger = logging.getLogger(__name__)

def create_member_accounts(user):
    """
    Creates default Savings, Venture, and Loan accounts for a new member.
    """
    # Savings account creation
    savings_types = SavingsType.objects.all()
    created_savings = []
    for savings_type in savings_types:
        if not SavingsAccount.objects.filter(
            member=user, account_type=savings_type
        ).exists():
            account = SavingsAccount.objects.create(
                member=user, account_type=savings_type, is_active=True
            )
            created_savings.append(str(account))
    logger.info(
        f"Created {len(created_savings)} SavingsAccounts for {user.member_no}: {', '.join(created_savings)}"
    )

    # Venture account creation
    venture_types = VentureType.objects.all()
    created_ventures = []
    for venture_type in venture_types:
        if not VentureAccount.objects.filter(
            member=user, venture_type=venture_type
        ).exists():
            account = VentureAccount.objects.create(
                member=user, venture_type=venture_type, is_active=True
            )
            created_ventures.append(str(account))
    logger.info(
        f"Created {len(created_ventures)} VentureAccounts for {user.member_no}: {', '.join(created_ventures)}"
    )

    # Loan account creation
    loan_types = LoanType.objects.all()
    created_loans = []
    for loan_type in loan_types:
        if not LoanAccount.objects.filter(
            member=user, loan_type=loan_type
        ).exists():
            account = LoanAccount.objects.create(
                member=user, loan_type=loan_type, is_active=True
            )
            created_loans.append(str(account))
    logger.info(
        f"Created {len(created_loans)} LoanAccounts for {user.member_no}: {', '.join(created_loans)}"
    )

    # Fee account creation
    fee_types = FeeType.objects.all()
    created_fees = []
    for fee_type in fee_types:
        if not MemberFee.objects.filter(
            member=user, fee_type=fee_type
        ).exists():
            account = MemberFee.objects.create(
                member=user, 
                fee_type=fee_type, 
                amount=fee_type.standard_amount,
                remaining_balance=fee_type.standard_amount
            )
            created_fees.append(str(account))
    logger.info(
        f"Created {len(created_fees)} MemberFees for {user.member_no}: {', '.join(created_fees)}"
    )
