import requests
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token

from django.conf import settings
from django.shortcuts import redirect
from urllib.parse import urlencode

from accounts.serializers import (
    BaseUserSerializer,
    MemberSerializer,
    SystemAdminSerializer,
    RequestPasswordResetSerializer,
    PasswordResetSerializer,
    UserLoginSerializer,
)
from accounts.permissions import IsSystemAdmin
from accounts.utils import send_password_reset_email, send_member_number_email


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
        return super().get_queryset().filter(id=self.request.user.id)


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
    Approve a new member
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
