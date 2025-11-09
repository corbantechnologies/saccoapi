from rest_framework import serializers

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
            "email",
            "address",
            "created_at",
            "updated_at",
            "reference",
        )
