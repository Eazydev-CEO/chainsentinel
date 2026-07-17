from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api.mixins import WorkspaceScopedViewSet
from apps.api.permissions import WorkspaceAccessPermission
from apps.api.workspace import resolve_workspace
from apps.audit.services import record_audit
from apps.workspaces.models import WorkspaceRole

from .models import Alert, AlertNote, AlertRule
from .serializers import (
    AlertDetailSerializer,
    AlertNoteSerializer,
    AlertRuleSerializer,
    AlertSerializer,
)


class AlertRuleViewSet(WorkspaceScopedViewSet):
    queryset = AlertRule.objects.all()
    serializer_class = AlertRuleSerializer
    read_role = WorkspaceRole.VIEWER
    write_role = WorkspaceRole.ADMIN
    search_fields = ["name", "description"]
    filterset_fields = ["is_active", "trigger_on", "severity"]
    ordering = ["-created_at"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["workspace"] = self.get_workspace()
        return context

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("chain", "wallet_monitor", "contract_monitor", "webhook")
        )

    def perform_create(self, serializer):
        super().perform_create(serializer)
        record_audit(
            request=self.request, action="alert_rule.created",
            target=serializer.instance, workspace=self.get_workspace(),
        )

    def perform_update(self, serializer):
        serializer.save()
        record_audit(
            request=self.request, action="alert_rule.updated",
            target=serializer.instance, workspace=serializer.instance.workspace,
        )

    def perform_destroy(self, instance):
        record_audit(
            request=self.request, action="alert_rule.deleted",
            workspace=instance.workspace, metadata={"name": instance.name},
        )
        instance.delete()


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    """Alerts are machine-created; humans acknowledge/resolve/annotate them."""

    permission_classes = [IsAuthenticated, WorkspaceAccessPermission]
    read_role = WorkspaceRole.VIEWER
    write_role = WorkspaceRole.ANALYST  # ack/resolve/notes are analyst duties
    filterset_fields = ["status", "severity", "rule"]
    search_fields = ["title", "message"]
    ordering_fields = ["created_at", "last_seen_at", "severity"]
    ordering = ["-created_at"]

    def get_queryset(self):
        workspace = resolve_workspace(self.request)
        if workspace is None:
            return Alert.objects.none()
        queryset = Alert.objects.filter(workspace=workspace).select_related(
            "rule", "event", "event__chain", "acknowledged_by", "resolved_by"
        )
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("notes__author")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AlertDetailSerializer
        return AlertSerializer

    @extend_schema(request=None, responses={200: AlertSerializer})
    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        if alert.status == Alert.Status.OPEN:
            alert.status = Alert.Status.ACKNOWLEDGED
            alert.acknowledged_by = request.user if request.user.pk else None
            alert.acknowledged_at = timezone.now()
            alert.save(update_fields=["status", "acknowledged_by", "acknowledged_at"])
            record_audit(
                request=request, action="alert.acknowledged", target=alert, workspace=alert.workspace
            )
        return Response(AlertSerializer(alert).data)

    @extend_schema(request=None, responses={200: AlertSerializer})
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        if alert.status != Alert.Status.RESOLVED:
            alert.status = Alert.Status.RESOLVED
            alert.resolved_by = request.user if request.user.pk else None
            alert.resolved_at = timezone.now()
            if alert.acknowledged_at is None:
                alert.acknowledged_at = alert.resolved_at
                alert.acknowledged_by = alert.resolved_by
            alert.save(
                update_fields=[
                    "status", "resolved_by", "resolved_at", "acknowledged_by", "acknowledged_at",
                ]
            )
            record_audit(
                request=request, action="alert.resolved", target=alert, workspace=alert.workspace
            )
            from apps.webhooks.services import dispatch_workspace_event

            dispatch_workspace_event(
                workspace=alert.workspace,
                event_type="alert.resolved",
                data={"alert_id": alert.pk, "title": alert.title, "severity": alert.severity},
                idempotency_suffix=f"alert:{alert.pk}:resolved",
            )
        return Response(AlertSerializer(alert).data)

    @extend_schema(request=AlertNoteSerializer, responses={201: AlertNoteSerializer})
    @action(detail=True, methods=["post"])
    def notes(self, request, pk=None):
        alert = self.get_object()
        serializer = AlertNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = AlertNote.objects.create(
            alert=alert,
            author=request.user if request.user.pk else None,
            body=serializer.validated_data["body"],
        )
        record_audit(request=request, action="alert.note_added", target=alert, workspace=alert.workspace)
        return Response(AlertNoteSerializer(note).data, status=status.HTTP_201_CREATED)
