"""API key authentication and scope enforcement."""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApiKey

from .conftest import DEMO_WALLET

pytestmark = pytest.mark.django_db


def make_key(workspace, user, scopes) -> tuple[str, ApiKey]:
    full, prefix, hashed = ApiKey.generate()
    api_key = ApiKey.objects.create(
        workspace=workspace, name="CI key", prefix=prefix, hashed_key=hashed,
        scopes=scopes, created_by=user,
    )
    return full, api_key


class TestApiKeyAuth:
    def test_read_scope_can_list(self, workspace, user, chain):
        full, _ = make_key(workspace, user, ["read"])
        client = APIClient()
        response = client.get(
            f"/api/v1/wallet-monitors/?workspace={workspace.pk}", HTTP_X_API_KEY=full
        )
        assert response.status_code == 200

    def test_key_workspace_is_implicit(self, workspace, user, chain):
        full, _ = make_key(workspace, user, ["read"])
        response = APIClient().get("/api/v1/wallet-monitors/", HTTP_X_API_KEY=full)
        assert response.status_code == 200  # workspace inferred from the key

    def test_read_scope_cannot_write(self, workspace, user, chain):
        full, _ = make_key(workspace, user, ["read"])
        response = APIClient().post(
            f"/api/v1/wallet-monitors/?workspace={workspace.pk}",
            {
                "name": "X", "address": DEMO_WALLET, "chain": "testnet",
                "event_types": ["native_transfer"],
            },
            format="json",
            HTTP_X_API_KEY=full,
        )
        assert response.status_code == 403

    def test_write_scope_can_create(self, workspace, user, chain):
        full, _ = make_key(workspace, user, ["read", "write"])
        response = APIClient().post(
            f"/api/v1/wallet-monitors/?workspace={workspace.pk}",
            {
                "name": "X", "address": DEMO_WALLET, "chain": "testnet",
                "event_types": ["native_transfer"],
            },
            format="json",
            HTTP_X_API_KEY=full,
        )
        assert response.status_code == 201, response.content

    def test_invalid_key_rejected(self, workspace, user):
        full, _ = make_key(workspace, user, ["read"])
        tampered = full[:-4] + "zzzz"
        response = APIClient().get(
            f"/api/v1/wallet-monitors/?workspace={workspace.pk}", HTTP_X_API_KEY=tampered
        )
        assert response.status_code == 401

    def test_revoked_key_rejected(self, workspace, user):
        full, api_key = make_key(workspace, user, ["read"])
        api_key.revoked_at = timezone.now()
        api_key.save()
        response = APIClient().get(
            f"/api/v1/wallet-monitors/?workspace={workspace.pk}", HTTP_X_API_KEY=full
        )
        assert response.status_code == 401

    def test_expired_key_rejected(self, workspace, user):
        from datetime import timedelta

        full, api_key = make_key(workspace, user, ["read"])
        api_key.expires_at = timezone.now() - timedelta(days=1)
        api_key.save()
        response = APIClient().get(
            f"/api/v1/wallet-monitors/?workspace={workspace.pk}", HTTP_X_API_KEY=full
        )
        assert response.status_code == 401

    def test_key_cannot_reach_foreign_workspace(self, workspace, user, make_user):
        from apps.workspaces.services import create_workspace

        stranger = make_user("stranger@example.com")
        other_workspace = create_workspace(name="Other", owner=stranger)
        full, _ = make_key(workspace, user, ["read", "write"])
        response = APIClient().get(
            f"/api/v1/wallet-monitors/?workspace={other_workspace.pk}", HTTP_X_API_KEY=full
        )
        assert response.status_code == 403

    def test_key_cannot_use_user_only_endpoints(self, workspace, user):
        full, _ = make_key(workspace, user, ["read", "write"])
        response = APIClient().get("/api/v1/auth/me/", HTTP_X_API_KEY=full)
        assert response.status_code == 403

    def test_last_used_is_tracked(self, workspace, user):
        full, api_key = make_key(workspace, user, ["read"])
        assert api_key.last_used_at is None
        APIClient().get(f"/api/v1/wallet-monitors/?workspace={workspace.pk}", HTTP_X_API_KEY=full)
        api_key.refresh_from_db()
        assert api_key.last_used_at is not None


class TestApiKeyLifecycleApi:
    def test_owner_creates_key_and_secret_shown_once(self, api, workspace):
        response = api.post(
            f"/api/v1/api-keys/?workspace={workspace.pk}",
            {"name": "CI", "scopes": ["read"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        body = response.json()
        assert body["key"].startswith("cs_")

        listed = api.get(f"/api/v1/api-keys/?workspace={workspace.pk}").json()
        assert "key" not in listed["results"][0]
        assert listed["results"][0]["prefix"] == body["prefix"]

    def test_revoke_key(self, api, workspace, user):
        full, api_key = make_key(workspace, user, ["read"])
        response = api.delete(f"/api/v1/api-keys/{api_key.pk}/?workspace={workspace.pk}")
        assert response.status_code == 200
        api_key.refresh_from_db()
        assert api_key.revoked_at is not None

    def test_unverified_owner_cannot_create_key(self, workspace, user):
        user.is_email_verified = False
        user.save()
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(
            f"/api/v1/api-keys/?workspace={workspace.pk}",
            {"name": "CI", "scopes": ["read"]},
            format="json",
        )
        assert response.status_code == 403
