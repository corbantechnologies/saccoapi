from rest_framework import serializers

from loans.models import LoanAccount
from loantypes.models import LoanType


class LoanAccountSerializer(serializers.ModelSerializer):
    loan_type = serializers.SlugRelatedField(
        slug_field="name", queryset=LoanType.objects.all()
    )
    user = serializers.CharField(source="user.member_no", read_only=True)
    approved_by = serializers.CharField(
        source="approved_by.member_no", read_only=True, required=False
    )

    class Meta:
        model = LoanAccount
        fields = [
            "user",
            "loan_type",
            "account_number",
            "loan_amount",
            "outstanding_balance",
            "interest_accrued",
            "is_active",
            "identity",
            "last_interest_calculation",
            "is_approved",
            "approval_date",
            "approved_by",
            "reference",
            "created_at",
            "updated_at",
        ]
