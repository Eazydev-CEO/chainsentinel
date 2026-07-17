"""Account business logic: registration, verification, resets, sessions."""
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError as JWTTokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.services import record_audit
from apps.notifications.emails import send_templated_email

from .models import User, UserProfile, UserSession
from .tokens import make_email_verification_token, make_password_reset_token

logger = logging.getLogger("chainsentinel.accounts")


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@transaction.atomic
def register_user(*, email: str, password: str, first_name: str = "", last_name: str = "") -> User:
    user = User.objects.create_user(
        email=email, password=password, first_name=first_name, last_name=last_name
    )
    UserProfile.objects.create(user=user)
    return user


def send_verification_email(user: User) -> None:
    token = make_email_verification_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    send_templated_email(
        to=[user.email],
        subject="Verify your ChainSentinel email",
        template="verify_email",
        context={"user": user, "link": link, "hours": settings.EMAIL_VERIFICATION_MAX_AGE // 3600},
    )


def send_password_reset_email(user: User) -> None:
    token = make_password_reset_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    send_templated_email(
        to=[user.email],
        subject="Reset your ChainSentinel password",
        template="password_reset",
        context={"user": user, "link": link, "hours": settings.PASSWORD_RESET_MAX_AGE // 3600},
    )


def issue_tokens_for_user(user: User, request) -> tuple[str, str]:
    """Create a refresh/access pair and record the device session."""
    refresh = RefreshToken.for_user(user)
    UserSession.objects.create(
        user=user,
        refresh_jti=str(refresh["jti"]),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
        ip_address=client_ip(request),
    )
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    return str(refresh.access_token), str(refresh)


def rotate_session(old_jti: str, new_refresh: RefreshToken) -> None:
    """Point the device session at the rotated refresh token."""
    UserSession.objects.filter(refresh_jti=old_jti, revoked_at__isnull=True).update(
        refresh_jti=str(new_refresh["jti"]), last_seen_at=timezone.now()
    )


def revoke_session(session: UserSession) -> None:
    """Revoke a device session and blacklist its refresh token."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    session.revoke()
    for token in OutstandingToken.objects.filter(jti=session.refresh_jti):
        BlacklistedToken.objects.get_or_create(token=token)


def revoke_all_sessions(user: User, except_jti: str | None = None) -> int:
    sessions = user.sessions.filter(revoked_at__isnull=True)
    if except_jti:
        sessions = sessions.exclude(refresh_jti=except_jti)
    count = 0
    for session in sessions:
        revoke_session(session)
        count += 1
    return count


def logout_user(request, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    try:
        token = RefreshToken(refresh_token)
        jti = str(token["jti"])
        session = UserSession.objects.filter(refresh_jti=jti).first()
        if session:
            revoke_session(session)
        else:
            token.blacklist()
    except JWTTokenError:
        # Already expired/blacklisted — nothing to clean up.
        pass
    if getattr(request, "user", None) and getattr(request.user, "is_authenticated", False):
        record_audit(request=request, action="auth.logout", target=request.user)
