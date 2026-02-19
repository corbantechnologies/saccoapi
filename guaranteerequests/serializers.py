from rest_framework import serializers
from decimal import Decimal

from guaranteerequests.models import GuaranteeRequest
from loanapplications.models import LoanApplication
from guarantorprofile.models import GuarantorProfile
from loanapplications.utils import compute_loan_coverage
from guaranteerequests.utils import send_guarantor_guarantee_request_status_email


class GuaranteeRequestSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)

    guarantor = serializers.SlugRelatedField(
        slug_field="member__member_no",
        queryset=GuarantorProfile.objects.filter(is_eligible=True),
    )
    loan_application = serializers.SlugRelatedField(
        slug_field="reference", queryset=LoanApplication.objects.all()
    )
    guaranteed_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=Decimal("0.01"), required=False, read_only=True
    )
    loan_application_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = GuaranteeRequest
        fields = (
            "member",
            "loan_application",
            "guarantor",
            "guaranteed_amount",
            "status",
            "notes",
            "created_at",
            "updated_at",
            "reference",
            "loan_application_detail",
        )

    def get_loan_application_detail(self, obj):
        loan = obj.loan_application
        snapshot = loan.projection_snapshot if loan.projection_snapshot else {}
        return {
            "reference": loan.reference,
            "requested_amount": loan.requested_amount,
            "repayment_amount": loan.repayment_amount,
            "total_interest": loan.total_interest,
            "status": loan.status,
            "term_months": snapshot.get("term_months"),
            "monthly_payment": loan.monthly_payment,
            "projection_snapshot": snapshot,
        }

    def validate(self, data):
        request = self.context["request"]
        member = request.user
        loan_app = data["loan_application"]
        guarantor = data["guarantor"]

        # 1. Ownership
        if loan_app.member != member:
            raise serializers.ValidationError(
                {
                    "loan_application": "You can only request guarantees for your own applications."
                }
            )

        # 2. Not in final state
        FINAL_STATES = ["Submitted", "Approved", "Disbursed", "Declined", "Cancelled"]
        if loan_app.status in FINAL_STATES:
            raise serializers.ValidationError(
                {"loan_application": f"Application is in '{loan_app.status}' state."}
            )

        # 3. No duplicate
        dup_qs = GuaranteeRequest.objects.filter(
            loan_application=loan_app, guarantor=guarantor
        )
        if self.instance:
            dup_qs = dup_qs.exclude(pk=self.instance.pk)
        if dup_qs.exists():
            raise serializers.ValidationError(
                {"guarantor": "This member is already a guarantor."}
            )

        return data

    def create(self, validated_data):
        validated_data["member"] = self.context["request"].user
        instance = super().create(validated_data)
        
        if instance.guarantor.member.email:
             send_guarantor_guarantee_request_status_email(instance)

        return instance


class GuaranteeApprovalDeclineSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=["Accepted", "Declined"], required=True)

    guaranteed_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False
    )

    class Meta:
        model = GuaranteeRequest
        fields = ("status", "guaranteed_amount")

    def validate(self, data):
        if data.get("status") == "Accepted":
            amount = data.get("guaranteed_amount")
            
            # 1. Amount required on acceptance
            if not amount:
                 raise serializers.ValidationError(
                    {"guaranteed_amount": "Amount is required when accepting."}
                )

            # 2. Positive amount
            if amount <= Decimal("0"):
                raise serializers.ValidationError(
                    {"guaranteed_amount": "Amount must be positive."}
                )

            instance = self.instance
            guarantor = instance.guarantor

            # 3. Check capacity
            # Note: We are checking against the *current* committed amount.
            # Since commitment is deferred to submission, this check ensures
            # the guarantor at least has "room" on paper right now.
            available = guarantor.available_capacity()

            if amount > available:
                raise serializers.ValidationError(
                    {
                        "guaranteed_amount": f"You only have {available} available guarantee limit."
                    }
                )
            
            # 4. Self-guarantee limit
            if guarantor.member == instance.loan_application.member:
                coverage = compute_loan_coverage(instance.loan_application)
                if amount > coverage["available_self_guarantee"]:
                    raise serializers.ValidationError(
                        {
                            "guaranteed_amount": f"Self-guarantee limited to {coverage['available_self_guarantee']}"
                        }
                    )
                    
        return data


class LoanApplicationGuaranteeRequestSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    guarantor = serializers.CharField(
        source="guarantor.member.member_no", read_only=True
    )

    class Meta:
        model = GuaranteeRequest
        fields = (
            "member",
            "guarantor",
            "guaranteed_amount",
            "status",
        )
