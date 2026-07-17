from rest_framework.permissions import BasePermission

from .models import ApiKeyPrincipal


class IsEmailVerified(BasePermission):
    """Sensitive writes require a verified email (API-key principals pass —
    key creation itself already required verification)."""

    message = "Verify your email address to perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if isinstance(user, ApiKeyPrincipal):
            return True
        return bool(user and user.is_authenticated and user.is_email_verified)


class IsRealUser(BasePermission):
    """Endpoint is for interactive users only (not API keys)."""

    message = "This endpoint is not available to API keys."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and not isinstance(request.user, ApiKeyPrincipal)
        )
