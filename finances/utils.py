from django.db import transaction
from decimal import Decimal
from datetime import date
import logging
from finances.models import GLAccount, JournalEntry, Journal, TransactionTemplate, TransactionTemplateLine

logger = logging.getLogger(__name__)

HARDCODED_MAPPINGS = {
    'savings_deposit': {'dr': '1010', 'cr': '2010', 'name': 'Savings Deposit'},
    'savings_withdrawal': {'dr': '2010', 'cr': '1010', 'name': 'Savings Withdrawal'},
    'venture_deposit': {'dr': '1010', 'cr': '2020', 'name': 'Venture Deposit'},
    'venture_payment': {'dr': '2020', 'cr': '1010', 'name': 'Venture Payment'},
    'loan_disbursement': {'dr': '1020', 'cr': '1010', 'name': 'Loan Disbursement'},
    'loan_repayment_principal': {'dr': '1010', 'cr': '1020', 'name': 'Loan Principal Repayment'},
    'loan_repayment_interest': {'dr': '1010', 'cr': '1030', 'name': 'Loan Interest Repayment'},
    'loan_interest_accrual': {'dr': '1030', 'cr': '4010', 'name': 'Loan Interest Accrual'},
    'fee_payment': {'dr': '1010', 'cr': '4020', 'name': 'Fee Payment'},
}

def get_or_create_template(transaction_type):
    template = TransactionTemplate.objects.filter(code=transaction_type).first()
    if template:
        return template
        
    if transaction_type in HARDCODED_MAPPINGS:
        mapping = HARDCODED_MAPPINGS[transaction_type]
        dr_code = mapping['dr']
        cr_code = mapping['cr']
        name = mapping['name']
        
        try:
            with transaction.atomic():
                template = TransactionTemplate.objects.create(
                    code=transaction_type,
                    name=name,
                    description=f"Auto-generated template for {name}"
                )
                dr_acc = GLAccount.objects.get(code=dr_code)
                cr_acc = GLAccount.objects.get(code=cr_code)
                
                TransactionTemplateLine.objects.create(
                    transaction_template=template,
                    gl_account=dr_acc,
                    is_debit=True
                )
                TransactionTemplateLine.objects.create(
                    transaction_template=template,
                    gl_account=cr_acc,
                    is_debit=False
                )
                return template
        except Exception as e:
            logger.error(f"Failed to auto-create template for {transaction_type}: {e}")
            return None
    return None

def post_to_gl(instance, transaction_type):
    """
    Centralized utility to post transactions to the General Ledger.
    Uses configurable Transaction Templates for balancing entries.
    """
    
    # Dynamic fee typing checks
    dr_code = '1010'
    cr_code = None
    if transaction_type == 'fee_payment' and hasattr(instance, 'member_fee'):
        fee_type = instance.member_fee.fee_type
        if fee_type.is_income:
            cr_code = '4020'
        elif fee_type.is_liability:
            cr_code = '2030'
        elif fee_type.is_equity:
            cr_code = '3020'
        elif fee_type.is_asset:
            cr_code = '1020'
        elif fee_type.is_expense:
            cr_code = '5010'

        if cr_code and cr_code != '4020':
            dynamic_code = f"fee_payment_{cr_code}"
            template = TransactionTemplate.objects.filter(code=dynamic_code).first()
            if not template:
                try:
                    with transaction.atomic():
                        template = TransactionTemplate.objects.create(
                            code=dynamic_code,
                            name=f"Fee Payment (CR {cr_code})",
                        )
                        dr_acc_obj = GLAccount.objects.get(code=dr_code)
                        cr_acc_obj = GLAccount.objects.get(code=cr_code)
                        TransactionTemplateLine.objects.create(transaction_template=template, gl_account=dr_acc_obj, is_debit=True)
                        TransactionTemplateLine.objects.create(transaction_template=template, gl_account=cr_acc_obj, is_debit=False)
                except Exception as e:
                    logger.error(f"Failed to create dynamic fee template: {e}")
                    return False
            transaction_type = dynamic_code

    template = get_or_create_template(transaction_type)
    if not template:
        logger.error(f"Invalid or missing transaction template for: {transaction_type}")
        return False
        
    try:
        with transaction.atomic():
            trans_date = getattr(instance, 'created_at', None)
            if trans_date:
                trans_date = trans_date.date()
            else:
                trans_date = date.today()
                
            amount = instance.amount
            description = str(instance)
            reference_id = str(instance.id)
            source_model = instance.__class__.__name__
            posted_by = getattr(instance, 'paid_by', getattr(instance, 'disbursed_by', getattr(instance, 'entered_by', getattr(instance, 'deposited_by', None))))

            # Create the compound journal header
            journal = Journal.objects.create(
                transaction_date=trans_date,
                description=description,
                reference_id=reference_id,
                source_model=source_model,
                template=template,
                posted_by=posted_by
            )
            
            lines = template.lines.all()
            if not lines.exists():
                raise Exception(f"Template {template.code} has no lines.")
                
            for line in lines:
                JournalEntry.objects.create(
                    journal=journal,
                    transaction_date=trans_date,
                    description=description,
                    gl_account=line.gl_account,
                    debit=amount if line.is_debit else 0,
                    credit=amount if not line.is_debit else 0,
                    reference_id=reference_id,
                    source_model=source_model,
                    posted_by=posted_by
                )
            
            logger.info(f"GL Posted via Journal {journal.id} for {source_model} {instance.id}")
            return True
            
    except Exception as e:
        logger.error(f"Error posting to GL: {str(e)}")
        return False
