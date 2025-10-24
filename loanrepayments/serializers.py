from rest_framework import serializers

from loanrepayments.models import LoanRepayment
from loans.models import LoanAccount
from decimal import Decimal


class LoanRepaymentSerializer(serializers.ModelSerializer):
    loan_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=LoanAccount.objects.all()
    )
    paid_by = serializers.CharField(source="paid_by.member_no", read_only=True)
    transaction_status = serializers.ChoiceField(
        choices=LoanRepayment.TRANSACTION_STATUS_CHOICES, default="Completed"
    )
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

    class Meta:
        model = LoanRepayment
        fields = [
            "loan_account",
            "paid_by",
            "amount",
            "payment_method",
            "repayment_type",
            "transaction_status",
            "receipt_number",
            "identity",
            "created_at",
            "updated_at",
            "reference",
        ]


class BulkLoanRepaymentSerializer(serializers.Serializer):
    repayments = LoanRepaymentSerializer(many=True)
