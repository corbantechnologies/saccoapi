from rest_framework import serializers
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.db import models

from loanapplications.models import LoanApplication
from loans.models import LoanAccount
from savings.models import SavingsAccount
from loantypes.models import LoanType
from loanapplications.calculators import reducing_fixed_payment, reducing_fixed_term
from guaranteerequests.models import GuaranteeRequest
from guarantorprofile.models import GuarantorProfile
from loanapplications.utils import compute_loan_coverage
from loans.serializers import MinimalLoanAccountSerializer
from guaranteerequests.serializers import LoanApplicationGuaranteeRequestSerializer


class LoanApplicationSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    product = serializers.SlugRelatedField(
        slug_field="name", queryset=LoanType.objects.all()
    )
    requested_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=1
    )
    start_date = serializers.DateField(default=date.today)
    can_submit = serializers.SerializerMethodField(read_only=True)
    projection = serializers.SerializerMethodField()
    loan_account = MinimalLoanAccountSerializer(read_only=True)
    guarantors = LoanApplicationGuaranteeRequestSerializer(many=True, read_only=True)
    # Computed fields
    total_savings = serializers.SerializerMethodField()
    available_self_guarantee = serializers.SerializerMethodField()
    total_guaranteed_by_others = serializers.SerializerMethodField()
    effective_coverage = serializers.SerializerMethodField()
    remaining_to_cover = serializers.SerializerMethodField()
    is_fully_covered = serializers.SerializerMethodField()

    class Meta:
        model = LoanApplication
        fields = (
            "member",
            "product",
            "requested_amount",
            "repayment_amount",
            "total_interest",
            "calculation_mode",
            "term_months",
            "monthly_payment",
            "repayment_frequency",
            "start_date",
            "status",
            "can_submit",
            "self_guaranteed_amount",
            "total_savings",
            "available_self_guarantee",
            "total_guaranteed_by_others",
            "effective_coverage",
            "remaining_to_cover",
            "is_fully_covered",
            "created_at",
            "updated_at",
            "reference",
            "loan_account",
            "guarantors",
            "projection",
        )

    # ===================================================================
    # Make fields optional on update
    # ===================================================================
    def get_fields(self):
        fields = super().get_fields()
        if self.instance:
            for f in [
                "product",
                "calculation_mode",
                "start_date",
                "repayment_frequency",
            ]:
                fields[f].required = False
            # Make term/monthly_payment optional on update
            fields["term_months"].required = False
            fields["monthly_payment"].required = False
        return fields

    def validate(self, data):
        """
        Only validate fields that are ACTUALLY being updated.
        """
        instance = getattr(self, "instance", None)
        partial = self.context["request"].method == "PATCH"

        # If partial update and key fields not in data → use instance values
        mode = data.get(
            "calculation_mode",
            getattr(instance, "calculation_mode", None) if instance else None,
        )
        product = data.get(
            "product", getattr(instance, "product", None) if instance else None
        )
        principal = data.get(
            "requested_amount",
            getattr(instance, "requested_amount", None) if instance else None,
        )
        term = data.get(
            "term_months", getattr(instance, "term_months", None) if instance else None
        )
        payment = data.get(
            "monthly_payment",
            getattr(instance, "monthly_payment", None) if instance else None,
        )
        start_date = data.get(
            "start_date",
            getattr(instance, "start_date", date.today()) if instance else date.today(),
        )
        frequency = data.get(
            "repayment_frequency",
            (
                getattr(instance, "repayment_frequency", "monthly")
                if instance
                else "monthly"
            ),
        )

        # Skip full validation if no calculation fields changed
        calc_fields = {
            "requested_amount",
            "calculation_mode",
            "term_months",
            "monthly_payment",
            "product",
            "start_date",
            "repayment_frequency",
        }
        if partial and not (set(data.keys()) & calc_fields):
            return data  # No recalc needed

        # --- FULL VALIDATION ONLY IF NEEDED ---
        if mode is None:
            raise serializers.ValidationError(
                {"calculation_mode": "This field is required."}
            )
        if product is None:
            raise serializers.ValidationError({"product": "This field is required."})
        if principal is None:
            raise serializers.ValidationError(
                {"requested_amount": "This field is required."}
            )

        # Mode-specific rules
        if mode == "fixed_term":
            if term is None:
                raise serializers.ValidationError(
                    {"term_months": "Required in 'fixed_term' mode."}
                )

        elif mode == "fixed_payment":
            if payment is None:
                raise serializers.ValidationError(
                    {"monthly_payment": "Required in 'fixed_payment' mode."}
                )

        else:
            raise serializers.ValidationError(
                {"calculation_mode": "Must be 'fixed_term' or 'fixed_payment'."}
            )

        # --- RECALCULATE PROJECTION ---
        try:
            if mode == "fixed_term":
                proj = reducing_fixed_term(
                    principal=principal,
                    annual_rate=product.interest_rate,
                    term_months=term,
                    start_date=start_date,
                    repayment_frequency=frequency,
                )
                data["monthly_payment"] = Decimal(proj["monthly_payment"])
                # data.pop("term_months", None)  <-- Don't remove the input!
            else:
                proj = reducing_fixed_payment(
                    principal=principal,
                    annual_rate=product.interest_rate,
                    payment_per_month=payment,
                    start_date=start_date,
                    repayment_frequency=frequency,
                )
                data["term_months"] = proj["term_months"]
                # data.pop("monthly_payment", None) <-- Don't remove the input!

            data["_projection"] = proj
            data["total_interest"] = Decimal(proj["total_interest"])
            data["repayment_amount"] = Decimal(proj["total_repayment"])

        except Exception as e:
            raise serializers.ValidationError(
                {"projection": f"Calculation failed: {str(e)}"}
            )

        return data

    # ===================================================================
    # 4. Create → save projection & mode
    # ===================================================================
    def create(self, validated_data):
        proj = validated_data.pop("_projection")
        instance = super().create(validated_data)

        instance.projection_snapshot = proj
        instance.monthly_payment = validated_data["monthly_payment"]
        instance.term_months = validated_data["term_months"]
        instance.total_interest = validated_data["total_interest"]
        instance.repayment_amount = validated_data["repayment_amount"]
        instance.save(
            update_fields=["projection_snapshot", "total_interest", "repayment_amount"]
        )

        # self._update_self_guarantee_and_status(instance)
        # Initial status is always Pending
        instance.status = "Pending"
        instance.save(update_fields=["status"])
        return instance

    # ===================================================================
    # 5. Update → recalc only if needed
    # ===================================================================
    def update(self, instance, validated_data):
        proj = validated_data.pop("_projection", None)
        instance = super().update(instance, validated_data)

        if proj:
            instance.projection_snapshot = proj
            instance.total_interest = validated_data.get(
                "total_interest", instance.total_interest
            )
            instance.repayment_amount = validated_data.get(
                "repayment_amount", instance.repayment_amount
            )
            instance.save(
                update_fields=[
                    "projection_snapshot",
                    "total_interest",
                    "repayment_amount",
                ]
            )

        # self._update_self_guarantee_and_status(instance)
        return instance

    # ===================================================================
    # 6. Self-guarantee & status logic
    # ===================================================================
    def _update_self_guarantee_and_status(self, instance):
        coverage = compute_loan_coverage(instance)

        # Only use what's needed for the loan
        instance.self_guaranteed_amount = min(
            Decimal(str(coverage["available_self_guarantee"])),
            Decimal(str(instance.requested_amount)),
        )

        # Recalculate coverage AFTER setting self_guaranteed_amount
        instance.save(update_fields=["self_guaranteed_amount"])
        coverage = compute_loan_coverage(instance)

        # Set status based on coverage ONLY if in appropriate state
        if instance.status in ["In Progress", "Amended"]:
            instance.status = (
                "Ready for Submission" if coverage["is_fully_covered"] else "In Progress"
            )
            instance.save(update_fields=["status"])

    # ===================================================================
    # 7. SerializerMethodFields
    # ===================================================================
    def get_projection(self, obj):
        return getattr(obj, "projection_snapshot", {})

    def get_total_savings(self, obj):
        total = SavingsAccount.objects.filter(member=obj.member).aggregate(
            t=models.Sum("balance")
        )["t"] or Decimal("0")
        return float(Decimal(total))

    def get_available_self_guarantee(self, obj):
        total_savings = Decimal(
            SavingsAccount.objects.filter(member=obj.member).aggregate(
                t=models.Sum("balance")
            )["t"]
            or "0"
        )

        committed_other = Decimal(
            GuaranteeRequest.objects.filter(
                guarantor__member=obj.member,
                status="Accepted",
                loan_application__status__in=["Submitted", "Approved", "Disbursed"],
            )
            .exclude(loan_application=obj)
            .aggregate(t=models.Sum("guaranteed_amount"))["t"]
            or "0"
        )

        available = total_savings - committed_other
        return float(max(Decimal("0"), available))

    def get_total_guaranteed_by_others(self, obj):
        total = obj.guarantors.filter(status="Accepted").aggregate(
            t=models.Sum("guaranteed_amount")
        )["t"]
        return float(total or 0)

    def get_effective_coverage(self, obj):
        self_guarantee = Decimal(str(obj.self_guaranteed_amount or 0))
        others = Decimal(str(self.get_total_guaranteed_by_others(obj)))
        return float(self_guarantee + others)

    def get_remaining_to_cover(self, obj):
        coverage = self.get_effective_coverage(obj)
        requested = Decimal(str(obj.requested_amount))
        return float(max(Decimal("0"), requested - Decimal(str(coverage))))

    def get_is_fully_covered(self, obj):
        return self.get_remaining_to_cover(obj) <= 0.01

    def get_can_submit(self, obj):
        return self.get_is_fully_covered(obj)


class LoanStatusUpdateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(
        choices=LoanApplication.STATUS_CHOICES, required=True
    )

    class Meta:
        model = LoanApplication
        fields = ("status",)
