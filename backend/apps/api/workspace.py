"""Workspace context resolution for API requests.

The active workspace is supplied via (in priority order):
  1. `X-Workspace-Id` header
  2. `?workspace=<id>` query parameter
  3. `workspace` field in the request body (create operations)

API-key principals are hard-bound to their key's workspace: any explicit
workspace reference must match it.
"""
from apps.accounts.models import ApiKeyPrincipal
from apps.workspaces.models import Workspace, WorkspaceMember

_ATTR = "_cs_workspace_cache"


def _requested_workspace_id(request) -> str | None:
    header = request.headers.get("X-Workspace-Id")
    if header:
        return header
    param = request.query_params.get("workspace") if hasattr(request, "query_params") else None
    if param:
        return param
    if hasattr(request, "data") and isinstance(request.data, dict):
        body = request.data.get("workspace")
        if body:
            return str(body)
    return None


def resolve_workspace(request) -> Workspace | None:
    """Return the active Workspace for this request, or None."""
    if hasattr(request, _ATTR):
        return getattr(request, _ATTR)

    workspace: Workspace | None = None
    requested = _requested_workspace_id(request)

    if isinstance(request.user, ApiKeyPrincipal):
        workspace = request.user.workspace
        if requested and str(workspace.pk) != str(requested):
            workspace = None  # key tried to reach a foreign workspace
    elif requested:
        try:
            workspace = Workspace.objects.get(pk=int(requested))
        except (Workspace.DoesNotExist, ValueError, TypeError):
            workspace = None

    setattr(request, _ATTR, workspace)
    return workspace


def get_role_for(request, workspace: Workspace) -> str | None:
    """Effective role of the request principal within `workspace`."""
    from apps.workspaces.models import WorkspaceRole

    user = request.user
    if isinstance(user, ApiKeyPrincipal):
        if user.workspace.pk != workspace.pk:
            return None
        # write scope acts as admin; read scope acts as viewer
        return WorkspaceRole.ADMIN if user.api_key.has_scope("write") else WorkspaceRole.VIEWER

    if not user.is_authenticated:
        return None
    member = WorkspaceMember.objects.filter(workspace=workspace, user=user).only("role").first()
    return member.role if member else None
