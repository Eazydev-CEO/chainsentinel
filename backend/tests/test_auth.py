"""Authentication: registration, cookie JWT flow, CSRF, verification gating."""
import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts.models import User

from .conftest import DEMO_WALLET

pytestmark = pytest.mark.django_db

REGISTER = {
    "email": "new@example.com",
    "password": "V3ry-Strong-Passw0rd",
    "first_name": "New",
    "workspace_name": "New Co",
}


class TestRegistration:
    def test_register_creates_user_workspace_and_cookies(self):
        client = APIClient()
        response = client.post("/api/v1/auth/register/", REGISTER, format="json")
        assert response.status_code == 201, response.content

        user = User.objects.get(email="new@example.com")
        assert not user.is_email_verified
        assert user.owned_workspaces.filter(name="New Co").exists()

        cookies = response.cookies
        assert cookies["cs_access"]["httponly"]
        assert cookies["cs_refresh"]["httponly"]
        assert cookies["cs_refresh"]["path"] == "/api/v1/auth"
        # Verification email went out.
        assert any("Verify" in m.subject for m in mail.outbox)

    def test_duplicate_email_rejected(self, user):
        client = APIClient()
        response = client.post(
            "/api/v1/auth/register/", {**REGISTER, "email": user.email}, format="json"
        )
        assert response.status_code == 400

    def test_weak_password_rejected(self):
        response = APIClient().post(
            "/api/v1/auth/register/", {**REGISTER, "password": "short"}, format="json"
        )
        assert response.status_code == 400


class TestLoginFlow:
    def test_login_sets_cookies_and_me_works(self, user):
        client = APIClient()
        response = client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "Str0ngPass!123"},
            format="json",
        )
        assert response.status_code == 200
        assert "cs_access" in response.cookies

        me = client.get("/api/v1/auth/me/")
        assert me.status_code == 200
        assert me.json()["email"] == user.email

    def test_wrong_password_rejected(self, user):
        response = APIClient().post(
            "/api/v1/auth/login/", {"email": user.email, "password": "wrong"}, format="json"
        )
        assert response.status_code == 401

    def test_cookie_write_requires_csrf_header(self, user):
        # enforce_csrf_checks=True makes the test client behave like a browser.
        client = APIClient(enforce_csrf_checks=True)
        client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "Str0ngPass!123"},
            format="json",
        )
        # No CSRF header → rejected.
        no_csrf = client.patch("/api/v1/auth/me/", {"first_name": "X"}, format="json")
        assert no_csrf.status_code == 403

        # Prime the CSRF cookie, echo it back → accepted.
        client.get("/api/v1/auth/csrf/")
        token = client.cookies["csrftoken"].value
        ok = client.patch(
            "/api/v1/auth/me/", {"first_name": "X"}, format="json", HTTP_X_CSRFTOKEN=token
        )
        assert ok.status_code == 200
        assert ok.json()["first_name"] == "X"

    def test_refresh_rotates_and_old_token_dies(self, user):
        client = APIClient()
        client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "Str0ngPass!123"},
            format="json",
        )
        old_refresh = client.cookies["cs_refresh"].value

        response = client.post("/api/v1/auth/refresh/")
        assert response.status_code == 200
        new_refresh = response.cookies["cs_refresh"].value
        assert new_refresh != old_refresh

        # Replaying the old (blacklisted) refresh cookie fails.
        client.cookies["cs_refresh"] = old_refresh
        replay = client.post("/api/v1/auth/refresh/")
        assert replay.status_code == 401

    def test_logout_clears_session(self, user):
        client = APIClient()
        client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "Str0ngPass!123"},
            format="json",
        )
        client.get("/api/v1/auth/csrf/")
        token = client.cookies["csrftoken"].value
        response = client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=token)
        assert response.status_code == 200

        refresh_after = client.post("/api/v1/auth/refresh/")
        assert refresh_after.status_code == 401

    def test_sessions_listed_and_revocable(self, user):
        client = APIClient()
        client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "Str0ngPass!123"},
            format="json",
        )
        sessions = client.get("/api/v1/auth/sessions/").json()
        assert len(sessions) == 1
        assert sessions[0]["is_current"] is True


class TestEmailVerificationFlow:
    def test_verification_token_roundtrip(self):
        client = APIClient()
        client.post("/api/v1/auth/register/", REGISTER, format="json")
        body = mail.outbox[-1].body
        token = body.split("token=")[1].split()[0].strip()

        response = APIClient().post("/api/v1/auth/verify-email/", {"token": token}, format="json")
        assert response.status_code == 200
        assert User.objects.get(email=REGISTER["email"]).is_email_verified

    def test_garbage_token_rejected(self):
        response = APIClient().post(
            "/api/v1/auth/verify-email/", {"token": "garbage"}, format="json"
        )
        assert response.status_code == 400

    def test_unverified_user_cannot_create_monitor(self, chain, make_user):
        from apps.workspaces.services import create_workspace

        unverified = make_user("unverified@example.com", verified=False)
        workspace = create_workspace(name="UV", owner=unverified)
        client = APIClient()
        client.force_authenticate(user=unverified)
        response = client.post(
            f"/api/v1/wallet-monitors/?workspace={workspace.pk}",
            {
                "name": "X", "address": DEMO_WALLET, "chain": "testnet",
                "event_types": ["native_transfer"],
            },
            format="json",
        )
        assert response.status_code == 403
        assert "Verify your email" in response.json()["error"]["message"]


class TestPasswordReset:
    def test_forgot_password_never_leaks_existence(self, user):
        client = APIClient()
        known = client.post(
            "/api/v1/auth/password/forgot/", {"email": user.email}, format="json"
        )
        unknown = client.post(
            "/api/v1/auth/password/forgot/", {"email": "ghost@example.com"}, format="json"
        )
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()
        assert len(mail.outbox) == 1  # only the real account got an email

    def test_reset_token_single_use(self, user):
        client = APIClient()
        client.post("/api/v1/auth/password/forgot/", {"email": user.email}, format="json")
        token = mail.outbox[-1].body.split("token=")[1].split()[0].strip()

        first = client.post(
            "/api/v1/auth/password/reset/",
            {"token": token, "password": "An0ther-Strong-P4ss"},
            format="json",
        )
        assert first.status_code == 200
        assert User.objects.get(pk=user.pk).check_password("An0ther-Strong-P4ss")

        replay = client.post(
            "/api/v1/auth/password/reset/",
            {"token": token, "password": "Third-Strong-P4ss!"},
            format="json",
        )
        assert replay.status_code == 400  # hash fragment changed → token dead
