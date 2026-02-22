from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from finances.models import GLAccount, JournalEntry
from django.db.models import Sum

class ReportingService:
    @staticmethod
    def post_transaction_to_gl(transaction_date, description, reference_id, source_model, postings):
        """
        postings: list of dicts {'account_code': '1010', 'debit': 100.0, 'credit': 0.0}
        """
        with transaction.atomic():
            entries = []
            for post in postings:
                gl_account = GLAccount.objects.get(code=post['account_code'])
                entry = JournalEntry(
                    transaction_date=transaction_date,
                    description=description,
                    gl_account=gl_account,
                    debit=Decimal(str(post.get('debit', 0))),
                    credit=Decimal(str(post.get('credit', 0))),
                    reference_id=str(reference_id),
                    source_model=source_model
                )
                entries.append(entry)
            
            # Basic validation: debits must equal credits
            total_debit = sum(e.debit for e in entries)
            total_credit = sum(e.credit for e in entries)
            
            if total_debit != total_credit:
                raise ValueError(f"Trial balance failed: Debit ({total_debit}) != Credit ({total_credit})")
                
            JournalEntry.objects.bulk_create(entries)

    @classmethod
    def post_savings_deposit(cls, deposit):
        """
        DR Bank (1010)
        CR Member Savings (2010)
        """
        cls.post_transaction_to_gl(
            transaction_date=deposit.created_at.date(),
            description=f"Savings Deposit: {deposit.savings_account.member.member_no} - {deposit.savings_account.account_type.name}",
            reference_id=deposit.id,
            source_model="SavingsDeposit",
            postings=[
                {'account_code': '1010', 'debit': deposit.amount, 'credit': 0},
                {'account_code': '2010', 'debit': 0, 'credit': deposit.amount},
            ]
        )

    @classmethod
    def post_loan_disbursement(cls, disb):
        """
        DR Loans Receivable (1020)
        CR Bank (1010)
        """
        cls.post_transaction_to_gl(
            transaction_date=disb.created_at.date(),
            description=f"Loan Disbursement: {disb.loan_account.member.member_no} - {disb.loan_account.loan_type.name}",
            reference_id=disb.id,
            source_model="LoanDisbursement",
            postings=[
                {'account_code': '1020', 'debit': disb.amount, 'credit': 0},
                {'account_code': '1010', 'debit': 0, 'credit': disb.amount},
            ]
        )

    @classmethod
    def post_loan_repayment(cls, rep):
        """
        DR Bank (1010)
        CR Loans Receivable (1020)
        """
        # Note: If it's an interest payment, it should CR Interest Receivable or Interest Income directly.
        # For now, simplistic principal repayment:
        if rep.repayment_type == "Interest Payment":
             cls.post_transaction_to_gl(
                transaction_date=rep.created_at.date(),
                description=f"Interest Payment: {rep.loan_account.member.member_no}",
                reference_id=rep.id,
                source_model="LoanRepayment",
                postings=[
                    {'account_code': '1010', 'debit': rep.amount, 'credit': 0},
                    {'account_code': '4010', 'debit': 0, 'credit': rep.amount},
                ]
            )
        else:
            cls.post_transaction_to_gl(
                transaction_date=rep.created_at.date(),
                description=f"Loan Principal Repayment: {rep.loan_account.member.member_no}",
                reference_id=rep.id,
                source_model="LoanRepayment",
                postings=[
                    {'account_code': '1010', 'debit': rep.amount, 'credit': 0},
                    {'account_code': '1020', 'debit': 0, 'credit': rep.amount},
                ]
            )

    @classmethod
    def post_venture_deposit(cls, v_dep):
        """
        DR Bank (1010)
        CR Venture Deposits (2020)
        """
        cls.post_transaction_to_gl(
            transaction_date=v_dep.created_at.date(),
            description=f"Venture Deposit: {v_dep.venture_account.member.member_no} - {v_dep.venture_account.venture_type.name}",
            reference_id=v_dep.id,
            source_model="VentureDeposit",
            postings=[
                {'account_code': '1010', 'debit': v_dep.amount, 'credit': 0},
                {'account_code': '2020', 'debit': 0, 'credit': v_dep.amount},
            ]
        )

    @classmethod
    def post_interest_accrual(cls, interest):
        """
        DR Interest Receivable (1030)
        CR Interest Income (4010)
        """
        cls.post_transaction_to_gl(
            transaction_date=interest.created_at.date(),
            description=f"Interest Accrued: {interest.loan_account.member.member_no}",
            reference_id=interest.id,
            source_model="TamarindLoanInterest",
            postings=[
                {'account_code': '1030', 'debit': interest.amount, 'credit': 0},
                {'account_code': '4010', 'debit': 0, 'credit': interest.amount},
            ]
        )
    @classmethod
    def post_savings_withdrawals(cls, withdrawal):
        """
        DR Member Savings (2010)
        CR Bank (1010)
        """
        cls.post_transaction_to_gl(
            transaction_date=withdrawal.created_at.date(),
            description=f"Savings Withdrawal: {withdrawal.savings_account.member.member_no}",
            reference_id=withdrawal.id,
            source_model="SavingsWithdrawal",
            postings=[
                {'account_code': '2010', 'debit': withdrawal.amount, 'credit': 0},
                {'account_code': '1010', 'debit': 0, 'credit': withdrawal.amount},
            ]
        )

    @classmethod
    def post_venture_payment(cls, v_pay):
        """
        DR Venture Deposits (2020)
        CR Bank (1010)
        """
        cls.post_transaction_to_gl(
            transaction_date=v_pay.created_at.date(),
            description=f"Venture Payment/Withdrawal: {v_pay.venture_account.member.member_no}",
            reference_id=v_pay.id,
            source_model="VenturePayment",
            postings=[
                {'account_code': '2020', 'debit': v_pay.amount, 'credit': 0},
                {'account_code': '1010', 'debit': 0, 'credit': v_pay.amount},
            ]
        )
