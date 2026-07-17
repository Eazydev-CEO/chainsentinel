"""Workspace-scoped permission classes (strict tenant isolation)."""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.workspaces.models import WorkspaceRole, role_at_least

from .workspace import get_role_for, resolve_workspace


class WorkspaceAccessPermission(BasePermission):
    """Requires an active-workspace context and sufficient role.

    Views declare:
        read_role  — minimum role for safe methods   (default: viewer)
        write_role — minimum role for unsafe methods (default: admin)
        role_overrides — optional {action_name: role} fine-tuning
    """

    message = "You do not have access to this workspace."

    def has_permission(self, request, view) -> bool:
        workspace = resolve_workspace(request)
        if workspace is None:
            self.message = (
                "Workspace context required. Pass ?workspace=<id> or the X-Workspace-Id header."
            )
            return False

        role = get_role_for(request, workspace)
        if role is None:
            self.message = "You are not a member of this workspace."
            return False

        if workspace.is_suspended and not getattr(request.user, "is_staff", False):
            self.message = "This workspace is suspended. Contact support."
            return False

        required = self._required_role(request, view)
        if not role_at_least(role, required):
            self.message = f"This action requires the {required} role or higher."
            return False
        return True

    def has_object_permission(self, request, view, obj) -> bool:
        workspace = resolve_workspace(request)
        if workspace is None:
            return False
        obj_workspace_id = getattr(obj, "workspace_id", None)
        if obj_workspace_id is None and hasattr(obj, "workspace"):
            obj_workspace_id = obj.workspace.pk
        return obj_workspace_id == workspace.pk

    @staticmethod
    def _required_role(request, view) -> str:
        overrides = getattr(view, "role_overrides", None) or {}
        action = getattr(view, "action", None)
        if action and action in overrides:
            return overrides[action]
        if request.method in SAFE_METHODS:
            return getattr(view, "read_role", WorkspaceRole.VIEWER)
        return getattr(view, "write_role", WorkspaceRole.ADMIN)
