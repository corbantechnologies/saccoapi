from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from feetypes.models import FeeType
from memberfees.models import MemberFee
from feetypes.serializers import FeeTypeSerializer

class MemberFeeSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    fee_type = serializers.SlugRelatedField(slug_field="name", queryset=FeeType.objects.all())
    
    class Meta:
        model = MemberFee
        fields = (
            "member",
            "fee_type",
            "amount",
            "account_number",
            "is_paid",
            "created_at",
            "updated_at",
            "reference",
        )


    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["fee_type"] = FeeTypeSerializer(instance.fee_type).data
        return representation