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
    savings_account_detail = serializers.SerializerMethodField()

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
            "savings_account_detail",
        )

    def validate(self, attrs):
        # Only validate savings_account if it is provided (i.e., during creation)
        if "savings_account" in attrs:
            savings_account = attrs["savings_account"]
            withdrawal_amount = attrs["amount"]
            if withdrawal_amount > savings_account.balance:
                raise serializers.ValidationError(
                    {"amount": "Withdrawal amount exceeds account balance."}
                )
        return super().validate(attrs)

    def get_savings_account_detail(self, obj):
        return {
            "account_number": obj.savings_account.account_number,
            "account_type": obj.savings_account.account_type.name,
            "balance": obj.savings_account.balance,
            "member": obj.savings_account.member.member_no,
        }
