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
)

app_name = "accounts"

urlpatterns = [
    path("token/", TokenView.as_view(), name="token"),
    path("signup/member/", MemberCreateView.as_view(), name="member"),
    path("signup/system-admin/", SystemAdminCreateView.as_view(), name="system-admin"),
    path(
        "approve-member/<str:reference>/",
        ApproveMemberView.as_view(),
        name="approve-member",
    ),
    path("<str:id>/", UserDetailView.as_view(), name="user-detail"),
    path("password/reset/", RequestPasswordResetView.as_view(), name="password-reset"),
    path("password/new/", PasswordResetView.as_view(), name="password-reset"),
]
