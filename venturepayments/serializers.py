from rest_framework import serializers

from venturepayments.models import VenturePayment
from ventures.models import VentureAccount


class VenturePaymentSerializer(serializers.ModelSerializer):
    venture_account = serializers.SlugRelatedField(
        queryset=VentureAccount.objects.all(), slug_field="account_number"
    )
    paid_by = serializers.CharField(source="paid_by.member_no", read_only=True)
    transaction_status = serializers.ChoiceField(
        choices=VenturePayment.TRANSACTION_STATUS_CHOICES, default="Completed"
    )

    class Meta:
        model = VenturePayment
        fields = (
            "venture_account",
            "paid_by",
            "amount",
            "payment_method",
            "payment_type",
            "transaction_status",
            "receipt_number",
            "identity",
            "created_at",
            "updated_at",
            "reference",
        )

    def validate(self, attrs):
        # Check if the payment amount exceeds the venture account balance
        if "venture_account" in attrs and "amount" in attrs:
            venture_account = attrs["venture_account"]
            payment_amount = attrs["amount"]
            if payment_amount > venture_account.balance:
                raise serializers.ValidationError(
                    {"amount": "Payment amount exceeds venture account balance."}
                )
        return super().validate(attrs)
