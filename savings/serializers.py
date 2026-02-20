from rest_framework import serializers

from savings.models import SavingsAccount
from savingstypes.models import SavingsType
from savingstypes.serializers import SavingsTypeSerializer
from savingsdeposits.serializers import SavingsDepositSerializer


class SavingsAccountSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    account_type = serializers.SlugRelatedField(
        queryset=SavingsType.objects.all(), slug_field="name"
    )
    deposits = SavingsDepositSerializer(many=True, read_only=True)

    class Meta:
        model = SavingsAccount
        fields = [
            "member",
            "account_type",
            "account_number",
            "balance",
            "is_active",
            "identity",
            "reference",
            "created_at",
            "updated_at",
            "deposits",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["account_type"] = SavingsTypeSerializer(instance.account_type).data
        return representation
