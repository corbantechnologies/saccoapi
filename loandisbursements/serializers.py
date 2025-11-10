from rest_framework import serializers
from django.contrib.auth import get_user_model

from loandisbursements.models import LoanDisbursement
from loans.models import LoanAccount

User = get_user_model()


class LoanDisbursementSerializer(serializers.ModelSerializer):
    loan_account = serializers.SlugRelatedField(
        queryset=LoanAccount.objects.all(), slug_field="account_number"
    )
    disbursed_by = serializers.CharField(
        source="disbursed_by.member_no", read_only=True
    )

    class Meta:
        model = LoanDisbursement
        fields = (
            "loan_account",
            "amount",
            "currency",
            "transaction_status",
            "disbursed_by",
            "disbursement_type",
            "created_at",
            "updated_at",
            "reference",
            "identity",
        )


class BulkLoanDisbursementSerializer(LoanDisbursementSerializer):
    disbursements = LoanDisbursementSerializer(many=True)
