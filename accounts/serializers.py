from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from accounts.validators import (
    validate_password_digit,
    validate_password_uppercase,
    validate_password_lowercase,
    validate_password_symbol,
)
from verification.models import VerificationCode
from accounts.utils import (
    send_registration_confirmation_email,
    send_account_created_by_admin_email,
)
from saccoapi.settings import DOMAIN
from savings.serializers import SavingsAccountSerializer
from loans.serializers import LoanAccountSerializer

User = get_user_model()


class BaseUserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=False,
    )
    password = serializers.CharField(
        max_length=128,
        min_length=5,
        write_only=True,
        validators=[
            validate_password_digit,
            validate_password_uppercase,
            validate_password_symbol,
            validate_password_lowercase,
        ],
    )
    avatar = serializers.ImageField(use_url=True, required=False)
    savings_accounts = SavingsAccountSerializer(many=True, read_only=True)
    loans = LoanAccountSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "password",
            "member_no",
            "salutation",
            "first_name",
            "last_name",
            "dob",
            "gender",
            "avatar",
            "id_type",
            "id_number",
            "tax_pin",
            "phone",
            "county",
            "employment_type",
            "employer",
            "job_title",
            "is_approved",
            "is_staff",
            "is_superuser",
            "is_member",
            "is_system_admin",
            "is_active",
            "created_at",
            "updated_at",
            "reference",
            "savings_accounts",
            "loans",
        )

    def create_user(self, validated_data, role_field):
        user = User.objects.create_user(**validated_data)
        setattr(user, role_field, True)
        user.is_active = True
        user.save()

        return user


class MemberSerializer(BaseUserSerializer):
    def create(self, validated_data):
        user = self.create_user(validated_data, "is_member")
        user.save()
        send_registration_confirmation_email(user)

        return user


class SystemAdminSerializer(BaseUserSerializer):
    def create(self, validated_data):
        user = self.create_user(validated_data, "is_system_admin")
        user.save()
        send_registration_confirmation_email(user)

        return user


"""
Password Reset Serializers
"""


class RequestPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, email):
        if not User.objects.filter(email=email).exists():
            raise serializers.ValidationError("Account with this email does not exist!")
        return email

    def save(self):
        email = self.validated_data.get("email")
        user = User.objects.get(email=email)

        # create verification code
        verification = VerificationCode.objects.create(
            user=user, purpose="password_reset"
        )

        return verification


class PasswordResetSerializer(serializers.Serializer):
    code = serializers.CharField()
    password = serializers.CharField(
        max_length=128,
        min_length=5,
        write_only=True,
        validators=[
            validate_password_digit,
            validate_password_uppercase,
            validate_password_symbol,
            validate_password_lowercase,
        ],
    )

    def validate(self, attrs):
        code = attrs.get("code")

        try:
            verification = VerificationCode.objects.get(
                code=code, purpose="password_reset", used=False
            )
        except VerificationCode.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired verification code!")

        if not verification.is_valid():
            raise serializers.ValidationError(
                "The code has expired or already been used!"
            )

        attrs["verification"] = verification
        attrs["user"] = verification.user
        return attrs

    def save(self):
        user = self.validated_data.get("user")
        verification = self.validated_data.get("verification")
        password = self.validated_data.get("password")

        # update password
        user.set_password(password)
        user.save()

        # mark code as used
        verification.used = True
        verification.save()

        return user


"""
Normal login
"""


class UserLoginSerializer(serializers.Serializer):
    member_no = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


"""
SACCO Admins Serializers
- They can create new members.
- The members are already approved.
- A password has to be set or they reset.
"""


class MemberCreatedByAdminSerializer(BaseUserSerializer):
    password = serializers.CharField(required=False, write_only=True)
    email = serializers.EmailField(required=False)

    def create(self, validated_data):
        # validated_data["password"] = None
        user = self.create_user(validated_data, "is_member")
        user.is_approved = True
        user.save()

        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        activation_link = f"{DOMAIN}/activate/{uid}/{token}"

        # Send member number email if email is provided
        if validated_data.get("email"):
            send_account_created_by_admin_email(user, activation_link)

        return user


class BulkMemberCreatedByAdminSerializer(serializers.Serializer):
    members = MemberCreatedByAdminSerializer(many=True)

    def create(self, validated_data):
        members_data = validated_data.get("members", [])
        created_members = []

        for member_data in members_data:
            serializer = MemberCreatedByAdminSerializer(data=member_data)
            serializer.is_valid(raise_exception=True)
            member = serializer.save()
            created_members.append(member)

        return created_members


# class BulkMemberCreatedByAdminSerializer(serializers.Serializer):
#     members = MemberCreatedByAdminSerializer(many=True)

#     def create(self, validated_data):
#         members_data = validated_data.get("members", [])
#         created_members = []
#         auto_generated_nos = []  # Track auto-generated member_nos for logging/response

#         with transaction.atomic():
#             for member_data in members_data:
#                 try:
#                     # Create a copy to avoid modifying original data
#                     member_dict = member_data.copy()

#                     # Handle member_no: if blank, let model auto-generate
#                     if not member_dict.get("member_no"):
#                         member_dict["member_no"] = (
#                             ""  # Ensure blank for auto-generation
#                         )
#                         auto_generated_nos.append(
#                             {
#                                 "index": len(created_members),
#                                 "data": {
#                                     k: v
#                                     for k, v in member_data.items()
#                                     if k != "member_no"
#                                 },
#                             }
#                         )

#                     # Email and phone are optional - remove if not provided to avoid unnecessary validation
#                     if "email" not in member_dict or not member_dict["email"]:
#                         del member_dict["email"]  # Skip if blank
#                     if "phone" not in member_dict or not member_dict["phone"]:
#                         del member_dict["phone"]  # Skip if blank

#                     serializer = MemberCreatedByAdminSerializer(data=member_dict)
#                     if serializer.is_valid(raise_exception=True):
#                         member = serializer.save()
#                         created_members.append(member)
#                     else:
#                         # If validation fails, collect error but continue (partial success)
#                         auto_generated_nos.append(
#                             {
#                                 "index": len(created_members),
#                                 "data": member_dict,
#                                 "errors": serializer.errors,
#                             }
#                         )
#                 except ValidationError as e:
#                     # Log validation errors but continue bulk
#                     auto_generated_nos.append(
#                         {
#                             "index": len(created_members),
#                             "data": member_data,
#                             "errors": e.detail,
#                         }
#                     )

#         # Response with summary
#         response_data = {
#             "created": len(created_members),
#             "members": created_members,
#         }
#         if auto_generated_nos:
#             response_data["auto_generated_member_nos"] = len(
#                 [g for g in auto_generated_nos if "member_no" not in g["data"]]
#             )
#             response_data["details"] = (
#                 auto_generated_nos  # Optional: include for debugging
#             )

#         if len(created_members) < len(members_data):
#             # Warn about partial success
#             response_data["warnings"] = (
#                 f"Created {len(created_members)} out of {len(members_data)} members. Check 'details' for issues."
#             )

#         return response_data
