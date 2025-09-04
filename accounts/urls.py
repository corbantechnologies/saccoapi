from django.urls import path

from accounts.views import (
    TokenView,
    MemberCreateView,
    SystemAdminCreateView,
    ApproveMemberView,
    UserDetailView,
    ApproveMemberView,
    RequestPasswordResetView,
    PasswordResetView,
    MemberDetailView,
    MemberListView,
)

app_name = "accounts"

urlpatterns = [
    path("token/", TokenView.as_view(), name="token"),
    path("signup/member/", MemberCreateView.as_view(), name="member"),
    path("signup/system-admin/", SystemAdminCreateView.as_view(), name="system-admin"),
    path("<str:id>/", UserDetailView.as_view(), name="user-detail"),
    # System admin activities
    path("", MemberListView.as_view(), name="members"),
    path("member/<str:member_no>/", MemberDetailView.as_view(), name="member-detail"),
    path(
        "approve-member/<str:member_no>/",
        ApproveMemberView.as_view(),
        name="approve-member",
    ),
    # Password reset
    path("password/reset/", RequestPasswordResetView.as_view(), name="password-reset"),
    path("password/new/", PasswordResetView.as_view(), name="password-reset"),
]
