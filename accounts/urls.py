from django.urls import path

from accounts.views import (
    TokenView,
    UserDetailView,
    RequestPasswordResetView,
    PasswordResetView,
    MemberDetailView,
    MemberListView,
    MemberCreatedByAdminView,
    ActivateAccountView,
    BulkMemberCreatedByAdminView,
    PasswordChangeView,
    BulkMemberCreatedByAdminUploadCSVView,
    AdminResetPasswordView
)

app_name = "accounts"

urlpatterns = [
    path("token/", TokenView.as_view(), name="token"),
    path("<str:id>/", UserDetailView.as_view(), name="user-detail"),
    # System admin activities
    path("members/all/", MemberListView.as_view(), name="members"),
    path("member/<str:member_no>/", MemberDetailView.as_view(), name="member-detail"),
    path(
        "member/<str:member_no>/reset-password/", 
        AdminResetPasswordView.as_view(), 
        name="admin-reset-password"
    ),
    path("new-member/create/", MemberCreatedByAdminView.as_view(), name="new-member"),
    path(
        "new-members/bulk-create/",
        BulkMemberCreatedByAdminView.as_view(),
        name="bulk-create-members",
    ),
    path(
        "new-members/bulk-create/upload/",
        BulkMemberCreatedByAdminUploadCSVView.as_view(),
        name="bulk-create-members-upload-csv",
    ),
    # Password reset
    path("password/forgot/", RequestPasswordResetView.as_view(), name="password-forgot"),
    path("password/reset/", PasswordResetView.as_view(), name="password-reset"),
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
    # Account activation
    path(
        "password/activate-account/",
        ActivateAccountView.as_view(),
        name="activate-account",
    ),
]
