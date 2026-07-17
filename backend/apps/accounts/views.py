import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError as JWTTokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.api.permissions import WorkspaceAccessPermission
from apps.api.workspace import resolve_workspace
from apps.audit.services import record_audit
from apps.workspaces.models import WorkspaceRole
from apps.workspaces.services import create_workspace

from . import services
from .cookies import clear_auth_cookies, set_auth_cookies
from .models import ApiKey, User, UserSession
from .permissions import IsRealUser
from .serializers import (
    ApiKeyCreateSerializer,
    ApiKeySerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    UserSessionSerializer,
    UserUpdateSerializer,
    VerifyEmailSerializer,
)
from .tokens import TokenError, check_email_verification_token, check_password_reset_token

logger = logging.getLogger("chainsentinel.accounts")


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """Prime the CSRF cookie for the SPA."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(operation_id="auth_csrf", responses={200: OpenApiResponse(description="CSRF cookie set")})
    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_register"

    @extend_schema(operation_id="auth_register", request=RegisterSerializer, responses={201: UserSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = services.register_user(
            email=data["email"],
            password=data["password"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
        )
        workspace_name = (data.get("workspace_name") or "").strip() or f"{user.full_name}'s Workspace"
        create_workspace(name=workspace_name, owner=user)
        services.send_verification_email(user)
        record_audit(request=request, action="auth.register", target=user, actor=user)

        access, refresh = services.issue_tokens_for_user(user, request)
        response = Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        set_auth_cookies(response, access, refresh)
        return response


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle, AnonRateThrottle]
    throttle_scope = "auth_login"

    @extend_schema(operation_id="auth_login", request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()
        password = serializer.validated_data["password"]

        user = authenticate(request, username=email, password=password)
        if user is None or not user.is_active:
            record_audit(
                request=request,
                action="auth.login_failed",
                metadata={"email": email},
            )
            return Response(
                {"error": {"code": "invalid_credentials", "message": "Invalid email or password.", "details": {}}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access, refresh = services.issue_tokens_for_user(user, request)
        record_audit(request=request, action="auth.login", target=user, actor=user)
        response = Response(UserSerializer(user).data)
        set_auth_cookies(response, access, refresh)
        return response


class RefreshView(APIView):
    """Rotate the refresh token from the HttpOnly cookie; re-issue both cookies."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(operation_id="auth_refresh", request=None, responses={200: OpenApiResponse(description="New token pair issued")})
    def post(self, request):
        raw = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if not raw:
            return Response(
                {"error": {"code": "no_refresh_token", "message": "No refresh token.", "details": {}}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            old = RefreshToken(raw)
            old_jti = str(old["jti"])
            user = User.objects.get(pk=old["user_id"], is_active=True)

            session = UserSession.objects.filter(refresh_jti=old_jti).first()
            if session is not None and not session.is_active:
                raise JWTTokenError("Session revoked.")

            old.blacklist()
            new_refresh = RefreshToken.for_user(user)
            services.rotate_session(old_jti, new_refresh)
        except (JWTTokenError, User.DoesNotExist):
            response = Response(
                {"error": {"code": "invalid_refresh_token", "message": "Session expired. Please sign in again.", "details": {}}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            clear_auth_cookies(response)
            return response

        response = Response({"detail": "Token refreshed."})
        set_auth_cookies(response, str(new_refresh.access_token), str(new_refresh))
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="auth_logout", request=None, responses={200: OpenApiResponse(description="Logged out")})
    def post(self, request):
        services.logout_user(request, request.COOKIES.get(settings.JWT_REFRESH_COOKIE))
        response = Response({"detail": "Logged out."})
        clear_auth_cookies(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated, IsRealUser]

    @extend_schema(operation_id="auth_me", responses={200: UserSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(operation_id="auth_me_update", request=UserUpdateSerializer, responses={200: UserSerializer})
    def patch(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_audit(request=request, action="account.profile_updated", target=request.user)
        return Response(UserSerializer(request.user).data)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_verify"

    @extend_schema(operation_id="auth_verify_email", request=VerifyEmailSerializer, responses={200: OpenApiResponse(description="Email verified")})
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = check_email_verification_token(serializer.validated_data["token"])
        except TokenError as exc:
            return Response(
                {"error": {"code": "invalid_token", "message": str(exc), "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.mark_email_verified()
        record_audit(request=request, action="auth.email_verified", target=user, actor=user)
        return Response({"detail": "Email verified. You now have full access."})


class ResendVerificationView(APIView):
    permission_classes = [IsAuthenticated, IsRealUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_verify"

    @extend_schema(operation_id="auth_resend_verification", request=None, responses={200: OpenApiResponse(description="Sent")})
    def post(self, request):
        if request.user.is_email_verified:
            return Response({"detail": "Email is already verified."})
        services.send_verification_email(request.user)
        return Response({"detail": "Verification email sent."})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_password_reset"

    @extend_schema(operation_id="auth_forgot_password", request=ForgotPasswordSerializer, responses={200: OpenApiResponse(description="Accepted")})
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            services.send_password_reset_email(user)
        # Same response either way — no account enumeration.
        return Response({"detail": "If that email exists, a reset link is on its way."})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_password_reset"

    @extend_schema(operation_id="auth_reset_password", request=ResetPasswordSerializer, responses={200: OpenApiResponse(description="Password reset")})
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = check_password_reset_token(serializer.validated_data["token"])
        except TokenError as exc:
            return Response(
                {"error": {"code": "invalid_token", "message": str(exc), "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        services.revoke_all_sessions(user)
        record_audit(request=request, action="auth.password_reset", target=user, actor=user)
        return Response({"detail": "Password updated. Please sign in."})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, IsRealUser]

    @extend_schema(operation_id="auth_change_password", request=ChangePasswordSerializer, responses={200: OpenApiResponse(description="Password changed")})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["current_password"]):
            return Response(
                {"error": {"code": "invalid_password", "message": "Current password is incorrect.", "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])

        # Keep this device signed in; sign out everything else.
        current_jti = self._current_jti(request)
        services.revoke_all_sessions(request.user, except_jti=current_jti)
        record_audit(request=request, action="auth.password_changed", target=request.user)

        access, refresh = services.issue_tokens_for_user(request.user, request)
        response = Response({"detail": "Password changed."})
        set_auth_cookies(response, access, refresh)
        return response

    @staticmethod
    def _current_jti(request) -> str | None:
        raw = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if not raw:
            return None
        try:
            return str(RefreshToken(raw)["jti"])
        except JWTTokenError:
            return None


class SessionListView(APIView):
    """Device/session management."""

    permission_classes = [IsAuthenticated, IsRealUser]

    @extend_schema(operation_id="auth_sessions", responses={200: UserSessionSerializer(many=True)})
    def get(self, request):
        current_jti = ChangePasswordView._current_jti(request)
        sessions = request.user.sessions.filter(revoked_at__isnull=True)
        serializer = UserSessionSerializer(sessions, many=True, context={"current_jti": current_jti})
        return Response(serializer.data)


class SessionRevokeView(APIView):
    permission_classes = [IsAuthenticated, IsRealUser]

    @extend_schema(operation_id="auth_session_revoke", request=None, responses={200: OpenApiResponse(description="Revoked")})
    def delete(self, request, session_id: int):
        session = request.user.sessions.filter(pk=session_id).first()
        if session is None:
            return Response(
                {"error": {"code": "not_found", "message": "Session not found.", "details": {}}},
                status=status.HTTP_404_NOT_FOUND,
            )
        services.revoke_session(session)
        record_audit(request=request, action="auth.session_revoked", target=request.user, metadata={"session_id": session_id})
        return Response({"detail": "Session revoked."})


class RevokeOtherSessionsView(APIView):
    permission_classes = [IsAuthenticated, IsRealUser]

    @extend_schema(operation_id="auth_sessions_revoke_others", request=None, responses={200: OpenApiResponse(description="Revoked")})
    def post(self, request):
        current_jti = ChangePasswordView._current_jti(request)
        count = services.revoke_all_sessions(request.user, except_jti=current_jti)
        record_audit(request=request, action="auth.sessions_revoked_others", target=request.user, metadata={"count": count})
        return Response({"detail": f"Revoked {count} other session(s)."})


class ApiKeyViewSet(viewsets.ModelViewSet):
    """Workspace API keys — owner only. The secret is returned exactly once."""

    serializer_class = ApiKeySerializer
    permission_classes = [IsAuthenticated, IsRealUser, WorkspaceAccessPermission]
    read_role = WorkspaceRole.OWNER
    write_role = WorkspaceRole.OWNER
    http_method_names = ["get", "post", "delete", "head", "options"]
    filterset_fields: list[str] = []
    search_fields = ["name", "prefix"]

    def get_queryset(self):
        workspace = resolve_workspace(self.request)
        if workspace is None:
            return ApiKey.objects.none()
        return ApiKey.objects.filter(workspace=workspace).select_related("created_by")

    def get_throttles(self):
        if self.action == "create":
            throttle = ScopedRateThrottle()
            throttle.scope = "api_key_create"
            return [throttle]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        from apps.accounts.permissions import IsEmailVerified

        if not IsEmailVerified().has_permission(request, self):
            return Response(
                {"error": {"code": "email_not_verified", "message": IsEmailVerified.message, "details": {}}},
                status=status.HTTP_403_FORBIDDEN,
            )
        workspace = resolve_workspace(request)
        serializer = ApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        full_key, prefix, hashed = ApiKey.generate()
        api_key = ApiKey.objects.create(
            workspace=workspace,
            name=serializer.validated_data["name"],
            prefix=prefix,
            hashed_key=hashed,
            scopes=serializer.validated_data["scopes"],
            expires_at=serializer.validated_data.get("expires_at"),
            created_by=request.user,
        )
        record_audit(request=request, action="api_key.created", target=api_key, workspace=workspace)
        data = ApiKeySerializer(api_key).data
        data["key"] = full_key  # shown once, never retrievable again
        return Response(data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        api_key = self.get_object()
        if api_key.revoked_at is None:
            api_key.revoked_at = timezone.now()
            api_key.save(update_fields=["revoked_at"])
            record_audit(request=request, action="api_key.revoked", target=api_key, workspace=api_key.workspace)
        return Response({"detail": "API key revoked."}, status=status.HTTP_200_OK)
