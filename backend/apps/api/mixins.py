"""Shared viewset behaviour for workspace-scoped resources."""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import ApiKeyPrincipal

from .permissions import WorkspaceAccessPermission
from .workspace import resolve_workspace


class WorkspaceScopedViewSet(viewsets.ModelViewSet):
    """Filters everything by the active workspace; stamps workspace/created_by on create.

    Subclasses set `queryset` (base manager) and the usual serializer bits.
    """

    permission_classes = [IsAuthenticated, WorkspaceAccessPermission]

    def get_workspace(self):
        return resolve_workspace(self.request)

    def get_queryset(self):
        workspace = self.get_workspace()
        if workspace is None:
            return self.queryset.none()
        return self.queryset.filter(workspace=workspace)

    def acting_user(self):
        """DB user for created_by fields (None for API-key principals)."""
        user = self.request.user
        if isinstance(user, ApiKeyPrincipal):
            return user.api_key.created_by
        return user

    def perform_create(self, serializer):
        kwargs = {"workspace": self.get_workspace()}
        model = serializer.Meta.model
        if any(f.name == "created_by" for f in model._meta.fields):
            kwargs["created_by"] = self.acting_user()
        serializer.save(**kwargs)
