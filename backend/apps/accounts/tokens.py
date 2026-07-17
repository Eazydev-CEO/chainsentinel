"""Signed, expiring single-purpose tokens (email verification, password reset).

Uses Django's cryptographic signing — no extra DB tables, tamper-proof,
and invalidated for password resets by embedding the password hash fragment
(so a used token can't be replayed after the password changes).
"""
from django.conf import settings
from django.core import signing

from .models import User

VERIFY_SALT = "chainsentinel.email-verify"
RESET_SALT = "chainsentinel.password-reset"


class TokenError(Exception):
    pass


def make_email_verification_token(user: User) -> str:
    return signing.dumps({"uid": user.pk, "email": user.email}, salt=VERIFY_SALT)


def check_email_verification_token(token: str) -> User:
    try:
        data = signing.loads(token, salt=VERIFY_SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)
    except signing.BadSignature as exc:
        raise TokenError("Invalid or expired verification link.") from exc
    try:
        user = User.objects.get(pk=data["uid"], email=data["email"])
    except (User.DoesNotExist, KeyError) as exc:
        raise TokenError("Invalid verification link.") from exc
    return user


def make_password_reset_token(user: User) -> str:
    # Embed a fragment of the current password hash: once the password changes,
    # the token stops validating.
    fragment = (user.password or "")[-12:]
    return signing.dumps({"uid": user.pk, "pw": fragment}, salt=RESET_SALT)


def check_password_reset_token(token: str) -> User:
    try:
        data = signing.loads(token, salt=RESET_SALT, max_age=settings.PASSWORD_RESET_MAX_AGE)
    except signing.BadSignature as exc:
        raise TokenError("Invalid or expired reset link.") from exc
    try:
        user = User.objects.get(pk=data["uid"])
    except (User.DoesNotExist, KeyError) as exc:
        raise TokenError("Invalid reset link.") from exc
    if (user.password or "")[-12:] != data.get("pw"):
        raise TokenError("This reset link has already been used.")
    return user
