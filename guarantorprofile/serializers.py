from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import models
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from guarantorprofile.models import GuarantorProfile
from savings.models import SavingsAccount
from guaranteerequests.serializers import GuaranteeRequestSerializer

User = get_user_model()


class GuarantorProfileSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    member_no = serializers.CharField(write_only=True)

    guarantor_name = serializers.SerializerMethodField(read_only=True)
    active_guarantees_count = serializers.SerializerMethodField()
    committed_amount = serializers.SerializerMethodField()
    available_amount = serializers.SerializerMethodField()
    has_reached_limit = serializers.SerializerMethodField()
    guarantees = GuaranteeRequestSerializer(many=True, read_only=True)

    class Meta:
        model = GuarantorProfile
        fields = (
            "member_no",
            "member",
            "guarantor_name",
            "is_eligible",
            "max_active_guarantees",
            "active_guarantees_count",
            "committed_amount",
            "committed_guarantee_amount",
            "max_guarantee_amount",
            "available_amount",
            "has_reached_limit",
            "reference",
            "created_at",
            "updated_at",
            "guarantees",
        )

    def validate(self, data):

        member_no = data.get("member_no")
        if member_no:
            try:
                member = User.objects.get(member_no=member_no)
                if GuarantorProfile.objects.filter(member=member).exists():
                    raise serializers.ValidationError(
                        {"member_no": "Member already has a Guarantor Profile."}
                    )
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    {"member_no": "Member with this member number does not exist."}
                )
        return data

    def get_guarantor_name(self, obj):
        return obj.member.get_full_name()

    def get_active_guarantees_count(self, obj):
        return obj.active_guarantees_count()

    def get_committed_amount(self, obj):
        return float(obj.committed_guarantee_amount)

    def get_available_amount(self, obj):
        return float(obj.available_capacity())

    def get_has_reached_limit(self, obj):
        count = obj.active_guarantees_count()
        available_amount = obj.available_capacity()

        if available_amount <= 0:
            return True
        if count >= obj.max_active_guarantees:
            return True
        return False

    def create(self, validated_data):
        member_no = validated_data.pop("member_no")
        member = User.objects.get(member_no=member_no)

        total_savings = SavingsAccount.objects.filter(member=member).aggregate(
            total=models.Sum("balance")
        )["total"] or Decimal("0")

        profile = GuarantorProfile.objects.create(
            member=member,
            max_guarantee_amount=total_savings,
            committed_guarantee_amount=Decimal("0"),
            **validated_data,
        )
        return profile
