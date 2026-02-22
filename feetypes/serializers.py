from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from feetypes.models import FeeType


class FeeTypeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        validators=[UniqueValidator(queryset=FeeType.objects.all())],
    )
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    class Meta:
        model = FeeType
        fields = (
            "name",
            "description",
            "standard_amount",
            "is_active",
            "created_at",
            "updated_at",
            "reference",
        )
