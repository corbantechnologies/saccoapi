from rest_framework import serializers


from feespayments.models import FeePayment
from memberfees.models import MemberFee
from accounts.models import User
from django.core.validators import MinValueValidator


class FeePaymentSerializer(serializers.ModelSerializer):
    member_fee = serializers.SlugRelatedField(
        slug_field="account_number", queryset=MemberFee.objects.all()
    )
    paid_by = serializers.CharField(
        source="paid_by.member_no", read_only=True
    )

    class Meta:
        model = FeePayment
        fields = (
            "member_fee",
            "amount",
            "payment_method",
            "receipt_number",
            "paid_by",
            "created_at",
            "updated_at",
            "reference",
        )

class BulkFeePaymentSerializer(serializers.Serializer):
    fee_payments = FeePaymentSerializer(many=True)
