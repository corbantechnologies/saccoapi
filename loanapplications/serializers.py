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
            "projection",
        )

    # ----------------------------------------------------------------------
    # Computed fields
    # ----------------------------------------------------------------------
    def get_projection(self, obj):
        return getattr(obj, "projection_snapshot", {})

    def get_total_savings(self, obj):
        total = SavingsAccount.objects.filter(member=obj.member).aggregate(
            t=models.Sum("balance")
        )["t"]
        return float(total or 0)

    def get_available_self_guarantee(self, obj):
        savings = self.get_total_savings(obj)
        committed = GuaranteeRequest.objects.filter(
            guarantor__member=obj.member,
            status="Accepted",
            loan_application__status__in=["Submitted", "Approved", "Disbursed"],
        ).aggregate(t=models.Sum("guaranteed_amount"))["t"] or Decimal("0")
        outstanding = LoanAccount.objects.filter(
            member=obj.member, is_active=True
        ).aggregate(t=models.Sum("outstanding_balance"))["t"] or Decimal("0")
        available = Decimal(savings) - committed - outstanding
        return float(max(Decimal("0"), available))

    def get_total_guaranteed_by_others(self, obj):
        total = obj.guarantors.filter(status="Accepted").aggregate(
            t=models.Sum("guaranteed_amount")
        )["t"]
        return float(total or 0)

    def get_effective_coverage(self, obj):
        return self.get_available_self_guarantee(
            obj
        ) + self.get_total_guaranteed_by_others(obj)

    def get_remaining_to_cover(self, obj):
        coverage = self.get_effective_coverage(obj)
        return float(
            max(Decimal("0"), Decimal(obj.requested_amount) - Decimal(coverage))
        )

    def get_is_fully_covered(self, obj):
        return self.get_remaining_to_cover(obj) <= 0

    def get_can_submit(self, obj):
        return self.get_is_fully_covered(obj)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _is_first_loan(self, member):
        return not LoanAccount.objects.filter(member=member).exists()

    def _total_savings(self, member):
        total = SavingsAccount.objects.filter(member=member).aggregate(
            total=models.Sum("balance")
        )["total"]
        return total or Decimal("0")

    # ----------------------------------------------------------------------
    # Validation
    # ----------------------------------------------------------------------
    def validate(self, data):
        member = self.context["request"].user
        mode = data.get("calculation_mode")
        term = data.get("term_months")
        payment = data.get("monthly_payment")
        requested_amount = data.get("requested_amount")

        # Calculation Modes validation
        if not mode:
            raise serializers.ValidationError(
                {"calculation_mode": "This field is required."}
            )

        if mode == "fixed_term":
            if term is None:
                raise serializers.ValidationError(
                    {
                        "term_months": "This field is required when calculation_mode is fixed_term."
                    }
                )
            if payment is not None:
                raise serializers.ValidationError(
                    {
                        "monthly_payment": "This field should not be provided when using fixed_term."
                    }
                )
        elif mode == "fixed_payment":
            if payment is None:
                raise serializers.ValidationError(
                    {
                        "monthly_payment": "This field is required when calculation_mode is fixed_payment."
                    }
                )
            if term is not None:
                raise serializers.ValidationError(
                    {
                        "term_months": "This field should not be provided when using fixed_payment."
                    }
                )
        else:
            raise serializers.ValidationError(
                {"calculation_mode": "Invalid calculation_mode."}
            )

        # Requested amount
        if requested_amount is None:
            raise serializers.ValidationError(
                {"requested_amount": "This field is required."}
            )

        # -------------------------------------------------------------
        # Compute projection
        # -------------------------------------------------------------
        principal = data["requested_amount"]
        product = data["product"]
        start_date = data.get("start_date", date.today())
        frequency = data.get("repayment_frequency", "monthly")

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
            else:  # fixed_payment
                proj = reducing_fixed_payment(
                    principal=principal,
                    annual_rate=product.interest_rate,
                    payment_per_month=payment,
                    start_date=start_date,
                    repayment_frequency=frequency,
                )
                data["term_months"] = proj["term_months"]

            data["_projection"] = proj
            data["total_interest"] = Decimal(proj["total_interest"])
            data["repayment_amount"] = Decimal(proj["total_repayment"])

        except Exception as e:
            raise serializers.ValidationError(
                {"projection": f"Calculation failed: {str(e)}"}
            )

        return data

    # ------------------------------------------------------------------
    # 3. CREATE / UPDATE → write computed values
    # ------------------------------------------------------------------
    def create(self, validated_data):
        validated_data.pop("calculation_mode", None)
        proj = validated_data.pop("_projection")
        instance = super().create(validated_data)
        instance.projection_snapshot = proj
        instance.total_interest = validated_data["total_interest"]
        instance.save(update_fields=["projection_snapshot", "total_interest"])
        self._update_self_guarantee_and_status(instance)
        return instance

    def update(self, instance, validated_data):
        validated_data.pop("calculation_mode", None)
        proj = validated_data.pop("_projection", None)
        instance = super().update(instance, validated_data)
        if proj:
            instance.projection_snapshot = proj
            instance.total_interest = validated_data.get(
                "total_interest", instance.total_interest
            )
            instance.save(update_fields=["projection_snapshot", "total_interest"])
        self._update_self_guarantee_and_status(instance)
        return instance

    # ------------------------------------------------------------------
    # Helper: Self-guarantee + status
    # ------------------------------------------------------------------
    def _update_self_guarantee_and_status(self, instance):
        from guarantorprofile.models import GuarantorProfile
        from guaranteerequests.models import GuaranteeRequest

        # Total savings
        total_savings = SavingsAccount.objects.filter(member=instance.member).aggregate(
            t=models.Sum("balance")
        )["t"] or Decimal("0")

        # Committed guarantees (by this member)
        committed = GuaranteeRequest.objects.filter(
            guarantor__member=instance.member,
            status="Accepted",
            loan_application__status__in=["Submitted", "Approved", "Disbursed"],
        ).aggregate(t=models.Sum("guaranteed_amount"))["t"] or Decimal("0")

        # Outstanding loans
        outstanding = LoanAccount.objects.filter(
            member=instance.member, is_active=True
        ).aggregate(t=models.Sum("outstanding_balance"))["t"] or Decimal("0")

        available = total_savings - committed - outstanding
        self_guarantee = min(available, instance.requested_amount)

        instance.self_guaranteed_amount = self_guarantee
        instance.status = (
            "Ready for Submission"
            if self_guarantee == instance.requested_amount
            else "Pending"
        )
        instance.save(update_fields=["self_guaranteed_amount", "status"])
