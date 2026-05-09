"""Reusable DRF permission classes."""
from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Object-level: requires `obj.user == request.user` (or superuser).

    Pair with `IsAuthenticated` in `permission_classes`. Honoured by DRF
    only when `get_object` is used or `check_object_permissions` is
    called explicitly.
    """

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_superuser:
            return True
        owner = getattr(obj, "user", None)
        return owner is not None and owner == request.user
