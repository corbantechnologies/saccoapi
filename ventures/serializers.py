from rest_framework import serializers

from venturetypes.models import VentureType
from ventures.models import VentureAccount


class VentureAccountSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    venture_type = serializers.SlugRelatedField(
        slug_field="name", queryset=VentureType.objects.all()
    )

    class Meta:
        model = VentureAccount
        fields = (
            "member",
            "venture_type",
            "account_number",
            "balance",
            "is_active",
            "identity",
            "created_at",
            "updated_at",
            "reference",
        )
