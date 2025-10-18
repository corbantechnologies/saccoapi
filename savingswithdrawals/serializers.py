from rest_framework import serializers

from savingswithdrawals.models import SavingsWithdrawal
from savings.models import SavingsAccount


class SavingsWithdrawalSerializer(serializers.ModelSerializer):
    savings_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=SavingsAccount.objects.all()
    )
    withdrawn_by = serializers.CharField(
        source="withdrawn_by.member_no", read_only=True
    )

    class Meta:
        model = SavingsWithdrawal
        fields = (
            "savings_account",
            "withdrawn_by",
            "amount",
            "payment_method",
            "transaction_status",
            "receipt_number",
            "identity",
            "created_at",
            "updated_at",
            "reference",
        )

    def validate(self, attrs):
        # Check if the withdrawal amount is greater than the account balance
        savings_account = attrs["savings_account"]
        withdrawal_amount = attrs["amount"]

        if withdrawal_amount > savings_account.balance:
            raise serializers.ValidationError(
                {"amount": "Withdrawal amount exceeds account balance."}
            )
        return super().validate(attrs)
