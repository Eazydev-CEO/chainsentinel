"""HttpOnly auth-cookie helpers. Tokens never touch localStorage."""
from django.conf import settings
from rest_framework.response import Response

AUTH_PATH = "/api/v1/auth"


def set_auth_cookies(response: Response, access: str, refresh: str | None = None) -> None:
    access_max_age = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
    refresh_max_age = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())

    response.set_cookie(
        settings.JWT_ACCESS_COOKIE,
        access,
        max_age=access_max_age,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="Lax",
        path="/",
    )
    if refresh is not None:
        # Refresh token is only ever sent to the auth endpoints.
        response.set_cookie(
            settings.JWT_REFRESH_COOKIE,
            refresh,
            max_age=refresh_max_age,
            httponly=True,
            secure=settings.SECURE_COOKIES,
            samesite="Lax",
            path=AUTH_PATH,
        )
        # Non-HttpOnly marker with no sensitive content — lets the Next.js
        # middleware know a session probably exists (UX only, not security).
        response.set_cookie(
            settings.JWT_SESSION_MARKER_COOKIE,
            "1",
            max_age=refresh_max_age,
            httponly=False,
            secure=settings.SECURE_COOKIES,
            samesite="Lax",
            path="/",
        )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.JWT_ACCESS_COOKIE, path="/")
    response.delete_cookie(settings.JWT_REFRESH_COOKIE, path=AUTH_PATH)
    response.delete_cookie(settings.JWT_SESSION_MARKER_COOKIE, path="/")
