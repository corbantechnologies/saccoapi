from rest_framework import serializers
from django.contrib.auth import get_user_model

from loans.models import LoanAccount
from loantypes.models import LoanType

User = get_user_model()


class LoanAccountSerializer(serializers.ModelSerializer):
    loan_type = serializers.SlugRelatedField(
        slug_field="name", queryset=LoanType.objects.all()
    )
    user = serializers.CharField(source="user.member_no", read_only=True)
    member_no = serializers.CharField(write_only=True)
    approved_by = serializers.CharField(
        source="approved_by.member_no", read_only=True, required=False
    )

    class Meta:
        model = LoanAccount
        fields = [
            "user",
            "member_no",
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

    def create(self, validated_data):
        member_no = validated_data.pop("member_no")
        try:
            user = User.objects.get(member_no=member_no)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "User with this member number does not exist."
            )
        validated_data["user"] = user
        return super().create(validated_data)
