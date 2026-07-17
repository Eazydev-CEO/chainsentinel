"""Authentication classes: cookie-based JWT (browser) and API keys (integrations)."""
import hmac

from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import ApiKey, ApiKeyPrincipal

CSRF_EXEMPT_METHODS = ("GET", "HEAD", "OPTIONS", "TRACE")


class _CsrfCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


def enforce_csrf(request) -> None:
    """Run Django's CSRF machinery manually (cookie-authenticated writes only)."""
    check = _CsrfCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    """JWT from the `cs_access` HttpOnly cookie, or an Authorization: Bearer header.

    Cookie-sourced credentials on unsafe methods must pass a CSRF check —
    cookies are attached automatically by browsers, headers are not.
    """

    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = None
        from_cookie = False

        if header is not None:
            raw_token = self.get_raw_token(header)
        if raw_token is None:
            raw_token = request.COOKIES.get(settings.JWT_ACCESS_COOKIE)
            from_cookie = raw_token is not None

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        if from_cookie and request.method not in CSRF_EXEMPT_METHODS:
            enforce_csrf(request)

        return user, validated_token


class ApiKeyAuthentication(BaseAuthentication):
    """`X-Api-Key: cs_<prefix>_<secret>` authentication for external integrations.

    The principal is workspace-bound; scope checks happen in permission classes.
    """

    keyword = "X-Api-Key"

    def authenticate(self, request):
        raw = request.headers.get(self.keyword, "").strip()
        if not raw:
            return None
        if not raw.startswith("cs_") or raw.count("_") < 2:
            raise exceptions.AuthenticationFailed(_("Malformed API key."))

        prefix = raw.split("_", 2)[1]
        try:
            api_key = ApiKey.objects.select_related("workspace").get(prefix=prefix)
        except ApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed(_("Invalid API key."))

        if not hmac.compare_digest(api_key.hashed_key, ApiKey.hash_key(raw)):
            raise exceptions.AuthenticationFailed(_("Invalid API key."))
        if not api_key.is_valid:
            raise exceptions.AuthenticationFailed(_("API key is revoked or expired."))
        if api_key.workspace.suspended_at is not None:
            raise exceptions.AuthenticationFailed(_("Workspace is suspended."))

        api_key.mark_used()
        return ApiKeyPrincipal(api_key), api_key

    def authenticate_header(self, request):
        return self.keyword
