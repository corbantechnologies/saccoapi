from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from venturetypes.models import VentureType


class VentureTypeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        validators=[UniqueValidator(queryset=VentureType.objects.all())],
    )
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    class Meta:
        model = VentureType
        fields = (
            "name",
            "description",
            "interest_rate",
            "created_at",
            "updated_at",
            "reference",
        )
