from rest_framework import serializers

from savings.models import SavingsAccount
from savingstypes.models import SavingsType


class SavingsAccountSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    account_type = serializers.SlugRelatedField(
        queryset=SavingsType.objects.all(), slug_field="name"
    )

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
        ]
