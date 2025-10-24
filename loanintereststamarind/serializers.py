from rest_framework import serializers
from decimal import Decimal

from loanintereststamarind.models import TamarindLoanInterest
from loans.models import LoanAccount


class TamarindLoanInterestSerializer(serializers.ModelSerializer):
    loan_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=LoanAccount.objects.all()
    )
    entered_by = serializers.CharField(source="entered_by.member_no", read_only=True)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

    class Meta:
        model = TamarindLoanInterest
        fields = (
            "loan_account",
            "amount",
            "entered_by",
            "created_at",
            "updated_at",
            "reference",
        )


class BulkTamarindLoanInterestSerializer(serializers.Serializer):
    interests = TamarindLoanInterestSerializer(many=True)
