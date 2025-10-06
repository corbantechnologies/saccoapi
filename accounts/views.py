import logging
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import transaction
from rest_framework.throttling import UserRateThrottle

from accounts.serializers import (
    BaseUserSerializer,
    MemberSerializer,
    SystemAdminSerializer,
    RequestPasswordResetSerializer,
    PasswordResetSerializer,
    UserLoginSerializer,
    MemberCreatedByAdminSerializer,
    BulkMemberCreatedByAdminSerializer,
    PasswordChangeSerializer,
)
from accounts.permissions import IsSystemAdmin
from accounts.utils import (
    send_password_reset_email,
    send_member_number_email,
    send_account_activated_email,
)
from savings.models import SavingsAccount
from savingstypes.models import SavingsType

logger = logging.getLogger(__name__)

User = get_user_model()

"""
Authentication
"""


class TokenView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = UserLoginSerializer

    def post(self, request, format=None):
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            member_no = serializer.validated_data["member_no"]
            password = serializer.validated_data["password"]

            user = authenticate(member_no=member_no, password=password)

            if user:
                if user.is_approved:
                    token, created = Token.objects.get_or_create(user=user)
                    user_details = {
                        "id": user.id,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "member_no": user.member_no,
                        "reference": user.reference,
                        "is_member": user.is_member,
                        "is_system_admin": user.is_system_admin,
                        "is_active": user.is_active,
                        "is_staff": user.is_staff,
                        "is_superuser": user.is_superuser,
                        "is_approved": user.is_approved,
                        "last_login": user.last_login,
                        "token": token.key,
                    }
                    return Response(user_details, status=status.HTTP_200_OK)
                else:
                    return Response(
                        {"detail": ("User account is not verified.")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"detail": ("Unable to log in with provided credentials.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


"""
Create and Detail Views
"""


class MemberCreateView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = MemberSerializer
    queryset = User.objects.all()


class SystemAdminCreateView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SystemAdminSerializer
    queryset = User.objects.all()


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BaseUserSerializer
    queryset = User.objects.all()
    lookup_field = "id"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(id=self.request.user.id)
            .prefetch_related("savings_accounts", "loans")
        )


"""
System admin views
- Approve new members
- View list of members
"""


class MemberListView(generics.ListAPIView):
    """
    Fetch the list of members
    """

    permission_classes = (IsSystemAdmin,)
    serializer_class = BaseUserSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        """
        Fetch is_member and is_system_admin field
        Users with is_system_admin are also members
        """
        return super().get_queryset().filter(
            is_member=True
        ) | super().get_queryset().filter(is_system_admin=True)


class MemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View, update and delete a member
    """

    permission_classes = (IsSystemAdmin,)
    serializer_class = BaseUserSerializer
    queryset = User.objects.all()
    lookup_field = "member_no"


class ApproveMemberView(generics.RetrieveUpdateAPIView):
    """
    Approve a new member after self registration.
    Email is compulsory
    """

    permission_classes = (IsSystemAdmin,)
    serializer_class = BaseUserSerializer
    queryset = User.objects.all()
    lookup_field = "member_no"

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        # Validate that user is not already approved
        if instance.is_approved:
            return Response(
                {"detail": "User is already approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Approve user and assign member number
        instance.is_approved = True
        instance.is_active = True
        instance.save()

        # Create SavingsAccount for each SavingsType
        savings_types = SavingsType.objects.all()
        created_accounts = []
        for savings_type in savings_types:
            if not SavingsAccount.objects.filter(
                member=instance, account_type=savings_type
            ).exists():
                account = SavingsAccount.objects.create(
                    member=instance, account_type=savings_type, is_active=True
                )
                created_accounts.append(str(account))
        logger.info(
            f"Created {len(created_accounts)} SavingsAccounts for {instance.member_no}: {', '.join(created_accounts)}"
        )

        # Send member number email
        try:
            send_member_number_email(user=instance)
        except Exception as e:
            # Log the error (use your preferred logging mechanism)
            print(f"Failed to send email to {instance.email}: {str(e)}")
            return Response(
                {"detail": "User approved, but failed to send email."},
                status=status.HTTP_200_OK,
            )

        serializer = self.get_serializer(instance)
        return Response(
            {"detail": "User approved successfully.", "data": serializer.data},
            status=status.HTTP_200_OK,
        )


"""
Password Reset
"""


class RequestPasswordResetView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = RequestPasswordResetSerializer(data=request.data)

        if serializer.is_valid():
            verification = serializer.save()

            send_password_reset_email(verification.user, verification.code)

            return Response(
                {"message": "Password reset email sent successfully!"},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            return Response(
                {"message": "Password reset successful!"},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordChangeView(generics.UpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PasswordChangeSerializer
    throttle_classes = [UserRateThrottle]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return Response(
            {"detail": "Password changed successfully"}, status=status.HTTP_200_OK
        )


"""
SACCO Admins:
- Creating a new member
- Approving a new member
- Member activating their accounts
"""


class MemberCreatedByAdminView(generics.CreateAPIView):
    permission_classes = (IsSystemAdmin,)
    serializer_class = MemberCreatedByAdminSerializer
    queryset = User.objects.all()

    def perform_create(self, serializer):
        user = serializer.save()

        savings_types = SavingsType.objects.all()
        created_accounts = []
        for savings_type in savings_types:
            if not SavingsAccount.objects.filter(
                member=user, account_type=savings_type
            ).exists():
                account = SavingsAccount.objects.create(
                    member=user, account_type=savings_type, is_active=True
                )
                created_accounts.append(str(account))
        logger.info(
            f"Created {len(created_accounts)} SavingsAccounts for {user.member_no}: {', '.join(created_accounts)}"
        )


class BulkMemberCreatedByAdminView(APIView):
    permission_classes = (IsSystemAdmin,)

    def post(self, request):
        serializer = BulkMemberCreatedByAdminSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            users = serializer.save()

            # Your existing savings account creation logic
            for user in users:
                savings_types = SavingsType.objects.all()
                created_accounts = []
                for savings_type in savings_types:
                    if not SavingsAccount.objects.filter(
                        member=user, account_type=savings_type
                    ).exists():
                        account = SavingsAccount.objects.create(
                            member=user, account_type=savings_type, is_active=True
                        )
                        created_accounts.append(str(account))
                logger.info(
                    f"Created {len(created_accounts)} SavingsAccounts for {user.member_no}: {', '.join(created_accounts)}"
                )

            # FIXED: Use MemberCreatedByAdminSerializer for response (handles User instances)
            return Response(
                {
                    "message": f"Successfully created {len(users)} members.",
                    "members": MemberCreatedByAdminSerializer(  # Changed here
                        users, many=True
                    ).data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ActivateAccountView(APIView):
    permission_classes = [
        AllowAny,
    ]

    def patch(self, request):
        uidb64 = request.data.get("uidb64")
        token = request.data.get("token")
        password = request.data.get("password")

        if not all([uidb64, token, password]):
            return Response(
                {"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"error": "Invalid activation link"}, status=status.HTTP_400_BAD_REQUEST
            )

        token_generator = PasswordResetTokenGenerator()
        if token_generator.check_token(user, token):
            # Validate password using the serializer
            serializer = BaseUserSerializer(
                user, data={"password": password}, partial=True
            )
            if serializer.is_valid():
                user.set_password(password)
                user.is_active = True
                user.save()

                # Send member number email
                try:
                    send_account_activated_email(user)
                except Exception as e:
                    # Log the error (use your preferred logging mechanism)
                    logger.error(f"Failed to send email to {user.email}: {str(e)}")
                    # print(f"Failed to send email to {user.email}: {str(e)}")
                return Response(
                    {"message": "Account activated successfully"},
                    status=status.HTTP_200_OK,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST
        )
