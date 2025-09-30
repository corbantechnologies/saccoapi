from rest_framework import serializers

from savingsdeposits.models import SavingsDeposit
from savings.models import SavingsAccount


class SavingsDepositSerializer(serializers.ModelSerializer):
    savings_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=SavingsAccount.objects.all()
    )
    deposited_by = serializers.CharField(
        source="deposited_by.member_no", read_only=True
    )
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = SavingsDeposit
        fields = [
            "savings_account",
            "deposited_by",
            "amount",
            "phone_number",
            "description",
            "currency",
            "payment_method",
            "deposit_type",
            "transaction_status",
            "is_active",
            "receipt_number",
            "identity",
            "created_at",
            "updated_at",
            "reference",
        ]
