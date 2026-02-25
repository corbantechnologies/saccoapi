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

    def get_fees(self, obj):
        return [
            {
                "account_number": fee.account_number,
                "fee_type_name": fee.fee_type.name,
            }
            for fee in MemberFee.objects.filter(member=obj).select_related("fee_type")
        ]

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
        # Determine Member
        member = None
        if hasattr(instance, "savings_account"):
            member = instance.savings_account.member
            acc_no = instance.savings_account.account_number
            acc_type = instance.savings_account.account_type.name
        elif hasattr(instance, "venture_account"):
            member = instance.venture_account.member
            acc_no = instance.venture_account.account_number
            acc_type = instance.venture_account.venture_type.name
        elif hasattr(instance, "loan_account"):
            member = instance.loan_account.member
            acc_no = instance.loan_account.account_number
            acc_type = instance.loan_account.loan_type.name
        elif hasattr(instance, "member_fee"):
            member = instance.member_fee.member
            acc_no = instance.member_fee.account_number
            acc_type = instance.member_fee.fee_type.name

        trans_type = instance.__class__.__name__

        # Consistent mapping
        return {
            "member_no": member.member_no if member else "N/A",
            "member_name": (
                f"{member.first_name} {member.last_name}" if member else "N/A"
            ),
            "account_number": acc_no if "acc_no" in locals() else "N/A",
            "account_type": acc_type if "acc_type" in locals() else "N/A",
            "transaction_type": trans_type,
            "amount": float(instance.amount),
            "outstanding_balance": (
                float(getattr(instance.loan_account, "outstanding_balance", 0))
                if hasattr(instance, "loan_account")
                else None
            ),
            "payment_method": getattr(instance, "payment_method", "N/A"),
            "transaction_status": getattr(instance, "transaction_status", "Completed"),
            "transaction_date": instance.created_at,
            "details": getattr(
                instance,
                "description",
                getattr(
                    instance, "deposit_type", getattr(instance, "repayment_type", "N/A")
                ),
            ),
            "reference": getattr(instance, "reference", "N/A"),
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
