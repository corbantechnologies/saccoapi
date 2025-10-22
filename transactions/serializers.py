from rest_framework import serializers
from django.contrib.auth import get_user_model

from savings.models import SavingsAccount
from ventures.models import VentureAccount

User = get_user_model()


class AccountSerializer(serializers.ModelSerializer):
    savings_accounts = serializers.SerializerMethodField()
    venture_accounts = serializers.SerializerMethodField()
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "member_no",
            "member_name",
            "savings_accounts",
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

    def get_member_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
