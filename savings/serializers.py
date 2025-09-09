from rest_framework import serializers

from savings.models import SavingsAccount
from savingstypes.models import SavingsType


class SavingsAccountSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.member_no", read_only=True)
    account_type = serializers.SlugRelatedField(
        queryset=SavingsType.objects.all(), slug_field="name"
    )

    class Meta:
        model = SavingsAccount
        fields = [
            "user",
            "account_type",
            "account_number",
            "balance",
            "is_active",
            "identity",
            "reference",
            "created_at",
            "updated_at",
        ]
