from rest_framework import serializers
from django.db import models

from nextofkin.models import NextOfKin


class NextOfKinSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)

    class Meta:
        model = NextOfKin
        fields = (
            "member",
            "first_name",
            "last_name",
            "relationship",
            "phone",
            "percentage",
            "email",
            "address",
            "created_at",
            "updated_at",
            "reference",
        )

    def validate(self, data):
        percentage = data.get("percentage")

        if percentage is not None:
            if not (0 <= percentage <= 100):
                raise serializers.ValidationError(
                    {"percentage": "Percentage must be between 0 and 100."}
                )

        # Determine the member correctly
        if self.instance:
            member = self.instance.member
        else:
            request = self.context.get("request")
            if not request or not hasattr(request, "user"):
                raise serializers.ValidationError("User not found in request.")
            member = request.user

        # Calculate current total (excluding current instance on update)
        queryset = NextOfKin.objects.filter(member=member)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        current_total = queryset.aggregate(total=models.Sum("percentage"))["total"] or 0

        # Use incoming percentage, or keep existing one if not provided (partial update)
        new_percentage = percentage
        if new_percentage is None and self.instance:
            new_percentage = self.instance.percentage
        elif new_percentage is None:
            new_percentage = 0

        if current_total + new_percentage > 100:
            remaining = 100 - current_total
            raise serializers.ValidationError(
                {
                    "percentage": f"Total allocation cannot exceed 100%. "
                    f"Already allocated: {current_total}%. "
                    f"Maximum allowed now: {remaining}%."
                }
            )

        return data
