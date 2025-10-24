from rest_framework import serializers
from django.contrib.auth import get_user_model

from savings.models import SavingsAccount
from ventures.models import VentureAccount
from loans.models import LoanAccount
from loanintereststamarind.models import TamarindLoanInterest

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
