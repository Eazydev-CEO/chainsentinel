"""Workspace isolation and role-based access control."""
import pytest
from rest_framework.test import APIClient

from apps.workspaces.models import WorkspaceRole

from .conftest import DEMO_WALLET, OTHER_WALLET

pytestmark = pytest.mark.django_db


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def outsider(make_user):
    return make_user("outsider@example.com")


@pytest.fixture
def viewer(make_user, add_member):
    member = make_user("viewer@example.com")
    add_member(member, WorkspaceRole.VIEWER)
    return member


@pytest.fixture
def analyst(make_user, add_member):
    member = make_user("analyst@example.com")
    add_member(member, WorkspaceRole.ANALYST)
    return member


@pytest.fixture
def admin(make_user, add_member):
    member = make_user("admin@example.com")
    add_member(member, WorkspaceRole.ADMIN)
    return member


MONITOR_PAYLOAD = {
    "name": "Watch",
    "address": DEMO_WALLET,
    "chain": "testnet",
    "direction": "both",
    "event_types": ["native_transfer"],
}


class TestWorkspaceIsolation:
    def test_non_member_cannot_list_monitors(self, outsider, workspace, chain):
        response = client_for(outsider).get(f"/api/v1/wallet-monitors/?workspace={workspace.pk}")
        assert response.status_code == 403

    def test_missing_workspace_context_rejected(self, api):
        response = api.get("/api/v1/wallet-monitors/")
        assert response.status_code == 403
        assert "Workspace context required" in response.json()["error"]["message"]

    def test_objects_invisible_across_workspaces(self, api, user, chain, wallet_monitor, make_user):
        from apps.workspaces.services import create_workspace

        second = create_workspace(name="Second", owner=user)
        response = api.get(f"/api/v1/wallet-monitors/{wallet_monitor.pk}/?workspace={second.pk}")
        assert response.status_code == 404  # exists, but not in this tenant

    def test_events_scoped_to_workspace(self, api, user, workspace, chain, wallet_monitor):
        from decimal import Decimal

        from apps.events.models import BlockchainEvent
        from apps.workspaces.services import create_workspace

        event = BlockchainEvent.objects.create(
            workspace=workspace, chain=chain, wallet_monitor=wallet_monitor,
            event_type="native_received", block_number=1, block_hash="0x11", tx_hash="0x22",
            amount_wei=Decimal(1), confirmations_required=1, idempotency_key="iso:1",
        )
        second = create_workspace(name="Second", owner=user)
        listed = api.get(f"/api/v1/events/?workspace={second.pk}").json()
        assert listed["count"] == 0
        found = api.get(f"/api/v1/events/?workspace={workspace.pk}").json()
        assert found["count"] == 1
        assert found["results"][0]["id"] == event.pk


class TestRoleMatrix:
    def test_viewer_can_read_but_not_write(self, viewer, workspace, chain):
        client = client_for(viewer)
        assert client.get(f"/api/v1/wallet-monitors/?workspace={workspace.pk}").status_code == 200
        response = client.post(
            f"/api/v1/wallet-monitors/?workspace={workspace.pk}", MONITOR_PAYLOAD, format="json"
        )
        assert response.status_code == 403

    def test_analyst_cannot_create_monitors(self, analyst, workspace, chain):
        response = client_for(analyst).post(
            f"/api/v1/wallet-monitors/?workspace={workspace.pk}", MONITOR_PAYLOAD, format="json"
        )
        assert response.status_code == 403

    def test_admin_can_create_monitors(self, admin, workspace, chain):
        response = client_for(admin).post(
            f"/api/v1/wallet-monitors/?workspace={workspace.pk}", MONITOR_PAYLOAD, format="json"
        )
        assert response.status_code == 201, response.content

    def test_analyst_can_acknowledge_alert(self, analyst, workspace, chain, wallet_monitor):
        from apps.alerts.models import Alert

        alert = Alert.objects.create(
            workspace=workspace, title="Test alert", severity="high", dedupe_key="perm:1"
        )
        response = client_for(analyst).post(
            f"/api/v1/alerts/{alert.pk}/acknowledge/?workspace={workspace.pk}"
        )
        assert response.status_code == 200
        alert.refresh_from_db()
        assert alert.status == "acknowledged"
        assert alert.acknowledged_by == analyst

    def test_viewer_cannot_acknowledge_alert(self, viewer, workspace):
        from apps.alerts.models import Alert

        alert = Alert.objects.create(
            workspace=workspace, title="Test alert", severity="high", dedupe_key="perm:2"
        )
        response = client_for(viewer).post(
            f"/api/v1/alerts/{alert.pk}/acknowledge/?workspace={workspace.pk}"
        )
        assert response.status_code == 403

    def test_analyst_can_add_notes(self, analyst, workspace):
        from apps.alerts.models import Alert

        alert = Alert.objects.create(
            workspace=workspace, title="Notes", severity="low", dedupe_key="perm:3"
        )
        response = client_for(analyst).post(
            f"/api/v1/alerts/{alert.pk}/notes/?workspace={workspace.pk}",
            {"body": "Investigating."},
            format="json",
        )
        assert response.status_code == 201

    def test_admin_cannot_manage_api_keys(self, admin, workspace):
        # API keys are owner-only.
        response = client_for(admin).get(f"/api/v1/api-keys/?workspace={workspace.pk}")
        assert response.status_code == 403

    def test_owner_manages_api_keys(self, api, workspace):
        response = api.get(f"/api/v1/api-keys/?workspace={workspace.pk}")
        assert response.status_code == 200

    def test_audit_log_admin_or_owner_only(self, viewer, admin, workspace):
        assert (
            client_for(viewer).get(f"/api/v1/audit-logs/?workspace={workspace.pk}").status_code
            == 403
        )
        assert (
            client_for(admin).get(f"/api/v1/audit-logs/?workspace={workspace.pk}").status_code
            == 200
        )


class TestMemberManagement:
    def test_admin_cannot_promote_to_admin(self, admin, workspace, viewer):
        from apps.workspaces.models import WorkspaceMember

        membership = WorkspaceMember.objects.get(workspace=workspace, user=viewer)
        response = client_for(admin).patch(
            f"/api/v1/members/{membership.pk}/?workspace={workspace.pk}",
            {"role": "admin"},
            format="json",
        )
        assert response.status_code == 403

    def test_owner_can_promote_to_admin(self, api, workspace, viewer):
        from apps.workspaces.models import WorkspaceMember

        membership = WorkspaceMember.objects.get(workspace=workspace, user=viewer)
        response = api.patch(
            f"/api/v1/members/{membership.pk}/?workspace={workspace.pk}",
            {"role": "admin"},
            format="json",
        )
        assert response.status_code == 200
        membership.refresh_from_db()
        assert membership.role == "admin"

    def test_owner_cannot_be_removed(self, admin, api, workspace, user):
        from apps.workspaces.models import WorkspaceMember

        owner_membership = WorkspaceMember.objects.get(workspace=workspace, user=user)
        response = client_for(admin).delete(
            f"/api/v1/members/{owner_membership.pk}/?workspace={workspace.pk}"
        )
        assert response.status_code == 403

    def test_member_can_leave(self, viewer, workspace):
        from apps.workspaces.models import WorkspaceMember

        membership = WorkspaceMember.objects.get(workspace=workspace, user=viewer)
        response = client_for(viewer).delete(
            f"/api/v1/members/{membership.pk}/?workspace={workspace.pk}"
        )
        assert response.status_code == 204
        assert not WorkspaceMember.objects.filter(pk=membership.pk).exists()

    def test_workspace_delete_owner_only(self, admin, workspace):
        response = client_for(admin).delete(f"/api/v1/workspaces/{workspace.pk}/")
        assert response.status_code == 403


class TestSuspendedWorkspace:
    def test_suspended_workspace_blocks_members(self, api, workspace):
        from django.utils import timezone

        workspace.suspended_at = timezone.now()
        workspace.save()
        response = api.get(f"/api/v1/wallet-monitors/?workspace={workspace.pk}")
        assert response.status_code == 403
        assert "suspended" in response.json()["error"]["message"].lower()
