from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from savingstypes.models import SavingsType


class SavingsTypeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True,
        validators=[UniqueValidator(queryset=SavingsType.objects.all())],
    )
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    class Meta:
        model = SavingsType
        fields = (
            "name",
            "description",
            "created_at",
            "updated_at",
            "reference",
        )
