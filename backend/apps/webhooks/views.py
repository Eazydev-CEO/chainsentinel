from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.permissions import IsEmailVerified
from apps.api.mixins import WorkspaceScopedViewSet
from apps.api.permissions import WorkspaceAccessPermission
from apps.api.workspace import resolve_workspace
from apps.audit.services import record_audit
from apps.workspaces.models import WorkspaceRole

from .models import WebhookDelivery, WebhookEndpoint
from .serializers import WebhookDeliverySerializer, WebhookEndpointSerializer
from .services import create_delivery


class WebhookEndpointViewSet(WorkspaceScopedViewSet):
    queryset = WebhookEndpoint.objects.all()
    serializer_class = WebhookEndpointSerializer
    read_role = WorkspaceRole.VIEWER
    write_role = WorkspaceRole.ADMIN
    search_fields = ["name", "url"]
    filterset_fields = ["enabled"]
    ordering = ["-created_at"]

    def get_permissions(self):
        permissions = super().get_permissions()
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            permissions.append(IsEmailVerified())
        return permissions

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        secret = WebhookEndpoint.generate_secret()
        endpoint = WebhookEndpoint(
            workspace=self.get_workspace(),
            created_by=self.acting_user(),
            **serializer.validated_data,
        )
        endpoint.set_secret(secret)
        endpoint.save()
        record_audit(
            request=request, action="webhook.created", target=endpoint, workspace=endpoint.workspace
        )
        data = WebhookEndpointSerializer(endpoint).data
        data["secret"] = secret  # shown once — store it now
        return Response(data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        serializer.save()
        record_audit(
            request=self.request, action="webhook.updated",
            target=serializer.instance, workspace=serializer.instance.workspace,
        )

    def perform_destroy(self, instance):
        record_audit(
            request=self.request, action="webhook.deleted",
            workspace=instance.workspace, metadata={"name": instance.name, "url": instance.url},
        )
        instance.delete()

    @extend_schema(request=None)
    @action(detail=True, methods=["post"], url_path="regenerate-secret")
    def regenerate_secret(self, request, pk=None):
        endpoint = self.get_object()
        secret = WebhookEndpoint.generate_secret()
        endpoint.set_secret(secret)
        endpoint.save(update_fields=["secret_encrypted", "updated_at"])
        record_audit(
            request=request, action="webhook.secret_regenerated", target=endpoint,
            workspace=endpoint.workspace,
        )
        data = WebhookEndpointSerializer(endpoint).data
        data["secret"] = secret  # shown once
        return Response(data)

    @extend_schema(request=None, responses={202: WebhookDeliverySerializer})
    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        endpoint = self.get_object()
        delivery = create_delivery(
            endpoint=endpoint,
            event_type="test.ping",
            data={
                "message": "ChainSentinel webhook test",
                "endpoint": endpoint.name,
                "requested_by": getattr(request.user, "email", "api-key"),
            },
            idempotency_key=f"ep:{endpoint.pk}:test:{int(timezone.now().timestamp() * 1000)}",
        )
        record_audit(request=request, action="webhook.tested", target=endpoint, workspace=endpoint.workspace)
        return Response(
            WebhookDeliverySerializer(delivery).data if delivery else {"detail": "Test queued."},
            status=status.HTTP_202_ACCEPTED,
        )

    def get_throttles(self):
        if getattr(self, "action", None) == "test":
            throttle = ScopedRateThrottle()
            throttle.scope = "webhook_test"
            return [throttle]
        return super().get_throttles()


class WebhookDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, WorkspaceAccessPermission]
    serializer_class = WebhookDeliverySerializer
    read_role = WorkspaceRole.VIEWER
    write_role = WorkspaceRole.ADMIN
    filterset_fields = ["endpoint", "status", "event_type"]
    ordering = ["-created_at"]

    def get_queryset(self):
        workspace = resolve_workspace(self.request)
        if workspace is None:
            return WebhookDelivery.objects.none()
        return WebhookDelivery.objects.filter(workspace=workspace).select_related("endpoint")

    @extend_schema(request=None, responses={202: WebhookDeliverySerializer})
    @action(detail=True, methods=["post"])
    def replay(self, request, pk=None):
        original = self.get_object()
        replay_count = original.replays.count() + 1
        delivery = create_delivery(
            endpoint=original.endpoint,
            event_type=original.event_type,
            data=original.payload,
            idempotency_key=f"{original.idempotency_key}:replay:{replay_count}",
            replay_of=original,
        )
        if delivery is None:
            return Response(
                {"error": {"code": "replay_exists", "message": "This replay was already queued.", "details": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        record_audit(
            request=request, action="webhook.delivery_replayed",
            target=original.endpoint, workspace=original.workspace,
            metadata={"delivery_id": original.pk, "replay_id": delivery.pk},
        )
        return Response(WebhookDeliverySerializer(delivery).data, status=status.HTTP_202_ACCEPTED)
