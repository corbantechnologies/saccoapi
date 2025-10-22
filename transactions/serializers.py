from rest_framework import serializers
from django.contrib.auth import get_user_model

from savings.serializers import SavingsAccountSerializer
from loans.serializers import LoanAccountSerializer
from ventures.serializers import VentureAccountSerializer

User = get_user_model()


class AccountSerializer(serializers.ModelSerializer):
    savings_accounts = SavingsAccountSerializer(many=True, read_only=True)
    loans = LoanAccountSerializer(many=True, read_only=True)
    venture_accounts = VentureAccountSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "member_no",
            "first_name",
            "last_name",
            "savings_accounts",
            "loans",
            "venture_accounts",
        )
