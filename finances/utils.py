from django.db import transaction
from decimal import Decimal
from datetime import date
import logging
from finances.models import GLAccount, JournalEntry

logger = logging.getLogger(__name__)

def post_to_gl(instance, transaction_type):
    """
    Centralized utility to post transactions to the General Ledger.
    
    transaction_type mapping:
    - 'savings_deposit': DR 1010 (Bank) / CR 2010 (Savings Liability)
    - 'savings_withdrawal': DR 2010 (Savings Liability) / CR 1010 (Bank)
    - 'venture_deposit': DR 1010 (Bank) / CR 2020 (Venture Liability)
    - 'venture_payment': DR 2020 (Venture Liability) / CR 1010 (Bank)
    - 'loan_disbursement': DR 1020 (Loans Receivable) / CR 1010 (Bank)
    - 'loan_repayment_principal': DR 1010 (Bank) / CR 1020 (Loans Receivable)
    - 'loan_repayment_interest': DR 1010 (Bank) / CR 1030 (Interest Receivable)
    - 'loan_interest_accrual': DR 1030 (Interest Receivable) / CR 4010 (Interest Income)
    - 'fee_payment': DR 1010 (Bank) / CR 4020 (Membership Fees Revenue)
    """
    
    mappings = {
        'savings_deposit': {'dr': '1010', 'cr': '2010'},
        'savings_withdrawal': {'dr': '2010', 'cr': '1010'},
        'venture_deposit': {'dr': '1010', 'cr': '2020'},
        'venture_payment': {'dr': '2020', 'cr': '1010'},
        'loan_disbursement': {'dr': '1020', 'cr': '1010'},
        'loan_repayment_principal': {'dr': '1010', 'cr': '1020'},
        'loan_repayment_interest': {'dr': '1010', 'cr': '1030'},
        'loan_interest_accrual': {'dr': '1030', 'cr': '4010'},
        'fee_payment': {'dr': '1010', 'cr': '4020'},
    }
    
    if transaction_type not in mappings:
        logger.error(f"Invalid transaction type: {transaction_type}")
        return False
        
    dr_code = mappings[transaction_type]['dr']
    cr_code = mappings[transaction_type]['cr']

    # Dynamic mapping for fee_payment based on FeeType flags
    if transaction_type == 'fee_payment' and hasattr(instance, 'member_fee'):
        fee_type = instance.member_fee.fee_type
        if fee_type.is_income:
            cr_code = '4020'  # Membership Fees (Revenue)
        elif fee_type.is_liability:
            cr_code = '2030'  # Member Contributions (Liability)
        elif fee_type.is_equity:
            cr_code = '3020'  # Share Capital (Equity)
        elif fee_type.is_asset:
            cr_code = '1020'  # Receivables (Asset)
        elif fee_type.is_expense:
            cr_code = '5010'  # Expenses (Expense Recovery)
        else:
            cr_code = '2030'  # Default fallback
    
    try:
        with transaction.atomic():
            dr_acc = GLAccount.objects.get(code=dr_code)
            cr_acc = GLAccount.objects.get(code=cr_code)
            
            # Use created_at if available, otherwise today
            trans_date = getattr(instance, 'created_at', None)
            if trans_date:
                trans_date = trans_date.date()
            else:
                trans_date = date.today()
                
            amount = instance.amount
            description = str(instance)
            reference_id = str(instance.id)
            source_model = instance.__class__.__name__
            posted_by = getattr(instance, 'paid_by', getattr(instance, 'disbursed_by', getattr(instance, 'entered_by', None)))

            # DR Entry
            JournalEntry.objects.create(
                transaction_date=trans_date,
                description=description,
                gl_account=dr_acc,
                debit=amount,
                credit=0,
                reference_id=reference_id,
                source_model=source_model,
                posted_by=posted_by
            )
            
            # CR Entry
            JournalEntry.objects.create(
                transaction_date=trans_date,
                description=description,
                gl_account=cr_acc,
                debit=0,
                credit=amount,
                reference_id=reference_id,
                source_model=source_model,
                posted_by=posted_by
            )
            
            logger.info(f"GL Posted for {source_model} {instance.id}: DR {dr_code} / CR {cr_code}")
            return True
            
    except GLAccount.DoesNotExist as e:
        logger.error(f"Failed to post to GL: Required account ({dr_code} or {cr_code}) not found.")
        return False
    except Exception as e:
        logger.error(f"Error posting to GL: {str(e)}")
        return False
