from datetime import timedelta

from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.permissions import IsEmailVerified
from apps.api.mixins import WorkspaceScopedViewSet
from apps.audit.services import record_audit
from apps.workspaces.models import WorkspaceRole

from . import csv_io, services
from .models import ContractMonitor, MonitorCsvImport, WalletMonitor
from .serializers import (
    ContractMonitorSerializer,
    MonitorCsvImportSerializer,
    ParseAbiSerializer,
    WalletMonitorSerializer,
)


class MonitorViewSetBase(WorkspaceScopedViewSet):
    """Common list/create/detail behaviour for both monitor kinds."""

    read_role = WorkspaceRole.VIEWER
    write_role = WorkspaceRole.ADMIN
    search_fields = ["name", "address", "notes"]
    ordering_fields = ["created_at", "name", "last_event_at"]
    ordering = ["-created_at"]

    def get_permissions(self):
        permissions = super().get_permissions()
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            permissions.append(IsEmailVerified())
        return permissions

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["workspace"] = self.get_workspace()
        context["acting_user"] = self.acting_user() if self.get_workspace() else None
        return context

    def get_queryset(self):
        queryset = super().get_queryset().select_related("chain")
        chain = self.request.query_params.get("chain")
        if chain:
            queryset = queryset.filter(chain__slug=chain)
        is_active = self.request.query_params.get("is_active")
        if is_active in ("true", "false"):
            queryset = queryset.filter(is_active=is_active == "true")
        severity = self.request.query_params.get("severity")
        if severity:
            queryset = queryset.filter(severity=severity)
        tag = self.request.query_params.get("tag")
        if tag:
            queryset = queryset.filter(tags__contains=[tag.lower()])
        return queryset

    # -- lifecycle actions ---------------------------------------------------
    @extend_schema(request=None)
    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        monitor = self.get_object()
        monitor.is_active = False
        monitor.save(update_fields=["is_active", "updated_at"])
        record_audit(
            request=request, action=f"{self.audit_prefix}.paused", target=monitor,
            workspace=monitor.workspace,
        )
        return Response(self.get_serializer(monitor).data)

    @extend_schema(request=None)
    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        monitor = self.get_object()
        monitor.is_active = True
        monitor.error_count = 0
        monitor.last_error = ""
        monitor.save(update_fields=["is_active", "error_count", "last_error", "updated_at"])
        record_audit(
            request=request, action=f"{self.audit_prefix}.resumed", target=monitor,
            workspace=monitor.workspace,
        )
        return Response(self.get_serializer(monitor).data)

    # -- statistics ------------------------------------------------------------
    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        from apps.alerts.models import Alert
        from apps.events.models import BlockchainEvent

        monitor = self.get_object()
        now = timezone.now()
        events = BlockchainEvent.objects.filter(**{self.event_fk: monitor})
        alerts = Alert.objects.filter(event__in=events.values("pk"))

        by_type = list(
            events.values("event_type").annotate(count=Count("id")).order_by("-count")[:10]
        )
        daily = list(
            events.filter(created_at__gte=now - timedelta(days=14))
            .values_list("created_at__date")
            .annotate(count=Count("id"))
            .order_by("created_at__date")
        )
        return Response(
            {
                "monitor_id": monitor.pk,
                "total_events": events.count(),
                "events_24h": events.filter(created_at__gte=now - timedelta(hours=24)).count(),
                "events_7d": events.filter(created_at__gte=now - timedelta(days=7)).count(),
                "alerts_total": alerts.count(),
                "last_event_at": monitor.last_event_at,
                "last_processed_block": monitor.last_processed_block,
                "error_count": monitor.error_count,
                "last_error": monitor.last_error,
                "events_by_type": by_type,
                "events_daily": [{"date": str(d), "count": c} for d, c in daily],
            }
        )

    @action(detail=True, methods=["get"])
    def activity(self, request, pk=None):
        from apps.events.models import BlockchainEvent
        from apps.events.serializers import BlockchainEventListSerializer

        monitor = self.get_object()
        events = (
            BlockchainEvent.objects.filter(**{self.event_fk: monitor})
            .select_related("chain")
            .order_by("-block_number", "-log_index")[:50]
        )
        return Response(BlockchainEventListSerializer(events, many=True).data)


class WalletMonitorViewSet(MonitorViewSetBase):
    queryset = WalletMonitor.objects.all()
    serializer_class = WalletMonitorSerializer
    audit_prefix = "wallet_monitor"
    event_fk = "wallet_monitor"
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def perform_create(self, serializer):
        super().perform_create(serializer)
        record_audit(
            request=self.request,
            action="wallet_monitor.created",
            target=serializer.instance,
            workspace=self.get_workspace(),
        )

    def perform_destroy(self, instance):
        record_audit(
            request=self.request,
            action="wallet_monitor.deleted",
            workspace=instance.workspace,
            metadata={"name": instance.name, "address": instance.address},
        )
        instance.delete()

    @extend_schema(request=None, responses={201: MonitorCsvImportSerializer})
    @action(
        detail=False,
        methods=["post"],
        url_path="import-csv",
        parser_classes=[MultiPartParser, FormParser],
    )
    def import_csv(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"error": {"code": "no_file", "message": "Attach a CSV file in the 'file' field.", "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (upload.name or "").lower().endswith(".csv"):
            return Response(
                {"error": {"code": "bad_file_type", "message": "Only .csv files are accepted.", "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            report = csv_io.import_wallet_monitors(
                workspace=self.get_workspace(), uploaded_file=upload, created_by=self.acting_user()
            )
        except csv_io.CsvImportError as exc:
            return Response(
                {"error": {"code": "csv_invalid", "message": str(exc), "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record_audit(
            request=request,
            action="wallet_monitor.csv_imported",
            workspace=self.get_workspace(),
            metadata={
                "filename": report.filename,
                "created": report.created_count,
                "failed": report.failed_count,
            },
        )
        return Response(MonitorCsvImportSerializer(report).data, status=status.HTTP_201_CREATED)

    def get_throttles(self):
        if getattr(self, "action", None) == "import_csv":
            throttle = ScopedRateThrottle()
            throttle.scope = "csv_import"
            return [throttle]
        return super().get_throttles()

    @action(detail=False, methods=["get"], url_path="export-csv")
    def export_csv(self, request):
        workspace = self.get_workspace()
        csv_text = csv_io.export_wallet_monitors(workspace)
        response = HttpResponse(csv_text, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="chainsentinel-wallet-monitors-{workspace.slug}.csv"'
        )
        return response

    @extend_schema(responses={200: MonitorCsvImportSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="imports")
    def imports(self, request):
        reports = MonitorCsvImport.objects.filter(workspace=self.get_workspace())[:20]
        return Response(MonitorCsvImportSerializer(reports, many=True).data)


class ContractMonitorViewSet(MonitorViewSetBase):
    queryset = ContractMonitor.objects.all()
    serializer_class = ContractMonitorSerializer
    audit_prefix = "contract_monitor"
    event_fk = "contract_monitor"

    def get_queryset(self):
        return super().get_queryset().select_related("abi_document")

    def perform_create(self, serializer):
        super().perform_create(serializer)
        services.sync_subscriptions(serializer.instance)
        record_audit(
            request=self.request,
            action="contract_monitor.created",
            target=serializer.instance,
            workspace=self.get_workspace(),
        )

    def perform_update(self, serializer):
        serializer.save()
        services.sync_subscriptions(serializer.instance)
        record_audit(
            request=self.request,
            action="contract_monitor.updated",
            target=serializer.instance,
            workspace=serializer.instance.workspace,
        )

    def perform_destroy(self, instance):
        record_audit(
            request=self.request,
            action="contract_monitor.deleted",
            workspace=instance.workspace,
            metadata={"name": instance.name, "address": instance.address},
        )
        instance.delete()

    @extend_schema(request=ParseAbiSerializer)
    @action(detail=False, methods=["post"], url_path="parse-abi")
    def parse_abi(self, request):
        """Validate an ABI and list its events (used by the monitor form)."""
        serializer = ParseAbiSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "valid": True,
                "event_count": len(serializer.validated_data["events"]),
                "events": serializer.validated_data["events"],
            }
        )
