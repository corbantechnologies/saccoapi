from rest_framework.permissions import BasePermission


class IsSystemAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_system_admin

    def has_object_permission(self, request, view, obj):
        return request.user.is_system_admin
