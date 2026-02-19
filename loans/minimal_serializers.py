from rest_framework import serializers
from loans.models import LoanAccount

class MinimalLoanAccountSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)

    class Meta:
        model = LoanAccount
        fields = (
            "account_number",
            "outstanding_balance",
            "member",
        )
