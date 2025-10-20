from rest_framework import serializers

from venturedeposits.models import VentureDeposit
from ventures.models import VentureAccount


class VentureDepositSerializer(serializers.ModelSerializer):
    venture_account = serializers.SlugRelatedField(
        queryset=VentureAccount.objects.all(), slug_field="account_number"
    )
    deposited_by = serializers.CharField(
        source="deposited_by.member_no", read_only=True
    )

    class Meta:
        model = VentureDeposit
        fields = (
            "venture_account",
            "deposited_by",
            "amount",
            "identity",
            "created_at",
            "updated_at",
            "reference",
        )
