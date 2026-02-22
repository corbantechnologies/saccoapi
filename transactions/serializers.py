from rest_framework import serializers
from django.contrib.auth import get_user_model

from savings.models import SavingsAccount
from ventures.models import VentureAccount
from loans.models import LoanAccount
from loanintereststamarind.models import TamarindLoanInterest
from loanrepayments.models import LoanRepayment
from venturedeposits.models import VentureDeposit
from venturepayments.models import VenturePayment
from savingswithdrawals.models import SavingsWithdrawal
from savingsdeposits.models import SavingsDeposit
from loandisbursements.models import LoanDisbursement
from memberfees.models import MemberFee
from loanrepayments.models import LoanRepayment

User = get_user_model()


class AccountSerializer(serializers.ModelSerializer):
    savings_accounts = serializers.SerializerMethodField()
    venture_accounts = serializers.SerializerMethodField()
    loan_accounts = (
        serializers.SerializerMethodField()
    )  # ← Still use this name in output
    loan_interest = serializers.SerializerMethodField()
    loan_disbursements = serializers.SerializerMethodField()
    loan_repayments = serializers.SerializerMethodField()
    fees = serializers.SerializerMethodField()
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "member_no",
            "member_name",
            "savings_accounts",
            "venture_accounts",
            "loan_accounts",  # ← Output field
            "loan_interest",
            "loan_disbursements",
            "loan_repayments",
            "fees",
        )

    def get_savings_accounts(self, obj):
        return SavingsAccount.objects.filter(member=obj).values_list(
            "account_number", "account_type__name", "balance"
        )

    def get_venture_accounts(self, obj):
        return VentureAccount.objects.filter(member=obj).values_list(
            "account_number", "venture_type__name", "balance"
        )

    def get_loan_accounts(self, obj):
        return obj.loans.values_list(
            "account_number",
            "loan_type__name",
            "outstanding_balance",
        )

    def get_loan_interest(self, obj):
        """
        Returns: (amount, loan_account_number, loan_type_name, created_at)
        """
        return (
            TamarindLoanInterest.objects.filter(loan_account__member=obj)
            .select_related("loan_account__loan_type")
            .values_list(
                "amount",
                "loan_account__account_number",
                "loan_account__loan_type__name",
                "created_at",
            )
            .order_by("-created_at")
        )

    def get_loan_disbursements(self, obj):
        return (
            LoanDisbursement.objects.filter(loan_account__member=obj)
            .values_list(
                "amount",
                "loan_account__account_number",
                "loan_account__loan_type__name",
                "created_at",
            )
            .order_by("-created_at")
        )

    def get_loan_repayments(self, obj):
        return (
            LoanRepayment.objects.filter(loan_account__member=obj)
            .values_list(
                "amount",
                "loan_account__account_number",
                "loan_account__loan_type__name",
                "created_at",
            )
            .order_by("-created_at")
        )

    def get_member_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class BulkUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class MemberTransactionSerializer(serializers.Serializer):
    member_no = serializers.CharField(source="member.member_no", read_only=True)
    member_name = serializers.SerializerMethodField()
    account_number = serializers.CharField(read_only=True)
    account_type = serializers.CharField(read_only=True)
    transaction_type = serializers.CharField(read_only=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    outstanding_balance = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, allow_null=True
    )
    payment_method = serializers.CharField(read_only=True, allow_null=True)
    transaction_status = serializers.CharField(read_only=True, allow_null=True)
    transaction_date = serializers.DateTimeField(read_only=True)
    details = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        fields = [
            "member_no",
            "member_name",
            "account_number",
            "account_type",
            "transaction_type",
            "amount",
            "outstanding_balance",
            "payment_method",
            "transaction_status",
            "transaction_date",
            "details",
        ]

    def get_member_name(self, obj):
        return f"{obj.member.first_name} {obj.member.last_name}"

    def to_representation(self, instance):
        # Handle different transaction types
        if isinstance(instance, SavingsDeposit):
            return {
                "member_no": instance.account.member.member_no,
                "member_name": f"{instance.account.member.first_name} {instance.account.member.last_name}",
                "account_number": instance.account.account_number,
                "account_type": "Savings",
                "transaction_type": "Deposit",
                "amount": instance.amount,
                "outstanding_balance": None,
                "payment_method": instance.payment_method,
                "transaction_status": instance.transaction_status,
                "transaction_date": instance.created_at,
                "details": instance.deposit_type or "N/A",
            }
        elif isinstance(instance, SavingsWithdrawal):
            return {
                "member_no": instance.account.member.member_no,
                "member_name": f"{instance.account.member.first_name} {instance.account.member.last_name}",
                "account_number": instance.account.account_number,
                "account_type": "Savings",
                "transaction_type": "Withdrawal",
                "amount": instance.amount,
                "outstanding_balance": None,
                "payment_method": instance.payment_method,
                "transaction_status": instance.transaction_status,
                "transaction_date": instance.created_at,
                "details": "N/A",
            }
        elif isinstance(instance, VentureDeposit):
            return {
                "member_no": instance.account.member.member_no,
                "member_name": f"{instance.account.member.first_name} {instance.account.member.last_name}",
                "account_number": instance.account.account_number,
                "account_type": "Venture",
                "transaction_type": "Deposit",
                "amount": instance.amount,
                "outstanding_balance": None,
                "payment_method": instance.payment_method,
                "transaction_status": instance.transaction_status,
                "transaction_date": instance.created_at,
                "details": "N/A",
            }
        elif isinstance(instance, VenturePayment):
            return {
                "member_no": instance.account.member.member_no,
                "member_name": f"{instance.account.member.first_name} {instance.account.member.last_name}",
                "account_number": instance.account.account_number,
                "account_type": "Venture",
                "transaction_type": "Payment",
                "amount": instance.amount,
                "outstanding_balance": None,
                "payment_method": instance.payment_method,
                "transaction_status": instance.transaction_status,
                "transaction_date": instance.created_at,
                "details": instance.payment_type or "N/A",
            }
        elif isinstance(instance, LoanRepayment):
            return {
                "member_no": instance.loan.user.member_no,
                "member_name": f"{instance.loan.user.first_name} {instance.loan.user.last_name}",
                "account_number": instance.loan.account_number,
                "account_type": "Loan",
                "transaction_type": "Repayment",
                "amount": instance.amount,
                "outstanding_balance": instance.loan.outstanding_balance,
                "payment_method": instance.payment_method,
                "transaction_status": instance.transaction_status,
                "transaction_date": instance.created_at,
                "details": "N/A",
            }
        elif isinstance(instance, TamarindLoanInterest):
            return {
                "member_no": instance.loan_account.user.member_no,
                "member_name": f"{instance.loan_account.user.first_name} {instance.loan_account.user.last_name}",
                "account_number": instance.loan_account.account_number,
                "account_type": "Interest",
                "transaction_type": "Interest",
                "amount": instance.amount,
                "outstanding_balance": instance.loan_account.outstanding_balance,
                "payment_method": instance.payment_method or "N/A",
                "transaction_status": instance.transaction_status or "Completed",
                "transaction_date": instance.created_at,
                "details": "N/A",
            }
        return super().to_representation(instance)


class MonthlySummarySerializer(serializers.Serializer):
    month = serializers.CharField()
    savings = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2)
    )
    ventures = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2)
    )
    loans = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2)
    )

    total_savings = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    total_ventures = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    total_loans = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
