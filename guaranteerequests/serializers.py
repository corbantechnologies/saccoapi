from rest_framework import serializers
from decimal import Decimal

from guaranteerequests.models import GuaranteeRequest
from loanapplications.models import LoanApplication
from guarantorprofile.models import GuarantorProfile
from loanapplications.utils import compute_loan_coverage


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
        max_digits=15, decimal_places=2, min_value=Decimal("0.01")
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
        return {
            "requested_amount": loan.requested_amount,
            "repayment_amount": loan.repayment_amount,
            "total_interest": loan.total_interest,
            "status": loan.status,
            "term_months": loan.projection_snapshot["term_months"],
            "monthly_payment": loan.monthly_payment,
        }

    def validate(self, data):
        request = self.context["request"]
        member = request.user
        loan_app = data["loan_application"]
        guarantor = data["guarantor"]
        amount = data["guaranteed_amount"]

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

        # 3. Guarantor capacity
        current_committed = guarantor.committed_guarantee_amount
        if self.instance:
            current_committed -= self.instance.guaranteed_amount

        if current_committed + amount > guarantor.max_guarantee_amount:
            available = guarantor.max_guarantee_amount - current_committed
            raise serializers.ValidationError(
                {"guaranteed_amount": f"Guarantor has only {available} available."}
            )

        # 4. No duplicate
        dup_qs = GuaranteeRequest.objects.filter(
            loan_application=loan_app, guarantor=guarantor
        )
        if self.instance:
            dup_qs = dup_qs.exclude(pk=self.instance.pk)
        if dup_qs.exists():
            raise serializers.ValidationError(
                {"guarantor": "This member is already a guarantor."}
            )

        # 5. Self-guarantee limit
        if guarantor.member == member:
            coverage = compute_loan_coverage(loan_app)
            if amount > coverage["available_self_guarantee"]:
                raise serializers.ValidationError(
                    {
                        "guaranteed_amount": f"Self-guarantee limited to {coverage['available_self_guarantee']}"
                    }
                )

        return data

    def create(self, validated_data):
        validated_data["member"] = self.context["request"].user
        instance = super().create(validated_data)

        # AUTO-ACCEPT SELF-GUARANTEE ONLY
        if instance.guarantor.member == instance.member:
            instance.status = "Accepted"
            instance.save(update_fields=["status"])

            loan = instance.loan_application
            loan.self_guaranteed_amount = instance.guaranteed_amount
            loan.save(update_fields=["self_guaranteed_amount"])

            if compute_loan_coverage(loan)["is_fully_covered"]:
                loan.status = "Ready for Submission"
                loan.save(update_fields=["status"])

        return instance


class GuaranteeApprovalDeclineSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=["Accepted", "Declined"], required=True)

    class Meta:
        model = GuaranteeRequest
        fields = ("status",)


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
