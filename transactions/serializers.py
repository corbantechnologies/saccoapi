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

User = get_user_model()


class AccountSerializer(serializers.ModelSerializer):
    savings_accounts = serializers.SerializerMethodField()
    venture_accounts = serializers.SerializerMethodField()
    loan_accounts = serializers.SerializerMethodField()
    loan_interest = serializers.SerializerMethodField()
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "member_no",
            "member_name",
            "savings_accounts",
            "loan_accounts",
            "loan_interest",
            "venture_accounts",
        )

    def get_savings_accounts(self, obj):
        # fetch the saving type, account number, balance
        return (
            SavingsAccount.objects.filter(member=obj)
            .values_list("account_number", "account_type__name", "balance")
            .all()
        )

    def get_venture_accounts(self, obj):

        return (
            VentureAccount.objects.filter(member=obj)
            .values_list("account_number", "venture_type__name", "balance")
            .all()
        )

    def get_loan_accounts(self, obj):

        return (
            LoanAccount.objects.filter(user=obj)
            .values_list(
                "account_number",
                "loan_type__name",
                "outstanding_balance",
                "loan_amount",
            )
            .all()
        )

    def get_loan_interest(self, obj):

        return (
            TamarindLoanInterest.objects.filter(loan_account__user=obj)
            .values_list(
                "amount",
                "loan_account__account_number",
                "loan_account__outstanding_balance",
            )
            .all()
        )

    def get_member_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class MemberTransactionSerializer(serializers.Serializer):
    member_no = serializers.CharField(source="user.member_no", read_only=True)
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
        return f"{obj.user.first_name} {obj.user.last_name}"

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
