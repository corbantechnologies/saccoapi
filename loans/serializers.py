from rest_framework import serializers
from django.contrib.auth import get_user_model

from loans.models import LoanAccount
from loantypes.models import LoanType
from loanrepayments.serializers import LoanRepaymentSerializer
from loanintereststamarind.serializers import TamarindLoanInterestSerializer
from loandisbursements.serializers import LoanDisbursementSerializer

User = get_user_model()


class LoanAccountSerializer(serializers.ModelSerializer):
    loan_type = serializers.SlugRelatedField(
        slug_field="name", queryset=LoanType.objects.all()
    )
    member = serializers.CharField(source="member.member_no", read_only=True)
    member_no = serializers.CharField(write_only=True)
    is_active = serializers.BooleanField(default=True)
    repayments = LoanRepaymentSerializer(many=True, read_only=True)
    loan_disbursements = LoanDisbursementSerializer(many=True, read_only=True)
    loan_interests = TamarindLoanInterestSerializer(many=True, read_only=True)

    class Meta:
        model = LoanAccount
        fields = [
            "member",
            "member_no",
            "loan_type",
            "account_number",
            "outstanding_balance",
            "interest_accrued",
            "is_active",
            "identity",
            "last_interest_calculation",
            "reference",
            "created_at",
            "updated_at",
            "loan_disbursements",
            "repayments",
            "loan_interests",
        ]

    def create(self, validated_data):
        member_no = validated_data.pop("member_no")
        try:
            user = User.objects.get(member_no=member_no)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "User with this member number does not exist."
            )
        validated_data["member"] = user
        return super().create(validated_data)


class MinimalLoanAccountSerializer(serializers.ModelSerializer):

    member = serializers.CharField(source="member.member_no", read_only=True)

    class Meta:
        model = LoanAccount
        fields = (
            "account_number",
            "outstanding_balance",
            "member",
        )
