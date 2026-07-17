from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.api.permissions import WorkspaceAccessPermission
from apps.api.workspace import resolve_workspace
from apps.workspaces.models import WorkspaceRole

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Workspace audit trail — owners and admins only."""

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, WorkspaceAccessPermission]
    read_role = WorkspaceRole.ADMIN
    write_role = WorkspaceRole.OWNER
    filterset_fields = ["action"]
    search_fields = ["action", "target_label", "actor_label"]
    ordering = ["-created_at"]

    def get_queryset(self):
        workspace = resolve_workspace(self.request)
        if workspace is None:
            return AuditLog.objects.none()
        return AuditLog.objects.filter(workspace=workspace)
