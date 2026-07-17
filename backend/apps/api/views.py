"""Analytics endpoints (real DB aggregates — no fabricated metrics) + contact."""
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.alerts.models import Alert
from apps.chains.models import RpcProvider
from apps.events.models import BlockchainEvent
from apps.monitors.models import ContractMonitor, WalletMonitor
from apps.webhooks.models import WebhookDelivery

from .permissions import WorkspaceAccessPermission
from .workspace import resolve_workspace


@extend_schema(operation_id="analytics_overview", responses={200: dict})
@api_view(["GET"])
@permission_classes([IsAuthenticated, WorkspaceAccessPermission])
def analytics_overview(request):
    workspace = resolve_workspace(request)
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_ago = now - timedelta(hours=24)

    wallet_monitors = WalletMonitor.objects.filter(workspace=workspace)
    contract_monitors = ContractMonitor.objects.filter(workspace=workspace)
    events = BlockchainEvent.objects.filter(workspace=workspace)
    deliveries_24h = WebhookDelivery.objects.filter(workspace=workspace, created_at__gte=day_ago)

    delivery_stats = deliveries_24h.aggregate(
        total=Count("id"),
        ok=Count("id", filter=Q(status=WebhookDelivery.Status.SUCCESS)),
    )
    success_rate = (
        round(100 * delivery_stats["ok"] / delivery_stats["total"], 1)
        if delivery_stats["total"]
        else None
    )

    chain_ids = set(wallet_monitors.values_list("chain_id", flat=True)) | set(
        contract_monitors.values_list("chain_id", flat=True)
    )
    providers = RpcProvider.objects.filter(chain_id__in=chain_ids, is_active=True)
    provider_stats = providers.aggregate(
        total=Count("id"),
        healthy=Count("id", filter=Q(health_status=RpcProvider.HealthStatus.HEALTHY)),
    )

    return Response(
        {
            "active_monitors": wallet_monitors.filter(is_active=True).count()
            + contract_monitors.filter(is_active=True).count(),
            "total_monitors": wallet_monitors.count() + contract_monitors.count(),
            "events_today": events.filter(created_at__gte=today_start).count(),
            "events_24h": events.filter(created_at__gte=day_ago).count(),
            "critical_alerts_open": Alert.objects.filter(
                workspace=workspace, severity="critical", status=Alert.Status.OPEN
            ).count(),
            "open_alerts": Alert.objects.filter(
                workspace=workspace, status=Alert.Status.OPEN
            ).count(),
            "webhook_success_rate_24h": success_rate,
            "webhook_deliveries_24h": delivery_stats["total"],
            "providers_healthy": provider_stats["healthy"],
            "providers_total": provider_stats["total"],
            "transactions_monitored": events.values("tx_hash").distinct().count(),
        }
    )


@extend_schema(operation_id="analytics_charts", responses={200: dict})
@api_view(["GET"])
@permission_classes([IsAuthenticated, WorkspaceAccessPermission])
def analytics_charts(request):
    workspace = resolve_workspace(request)
    try:
        days = min(max(int(request.query_params.get("days", 14)), 1), 90)
    except ValueError:
        days = 14
    since = timezone.now() - timedelta(days=days)

    events = BlockchainEvent.objects.filter(workspace=workspace, created_at__gte=since)
    alerts = Alert.objects.filter(workspace=workspace, created_at__gte=since)
    deliveries = WebhookDelivery.objects.filter(workspace=workspace, created_at__gte=since)

    events_by_chain = list(
        events.annotate(date=TruncDate("created_at"))
        .values("date", "chain__slug")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    events_over_time = list(
        events.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(
            count=Count("id"),
            confirmed=Count("id", filter=Q(status="confirmed")),
        )
        .order_by("date")
    )
    alerts_by_severity = list(
        alerts.values("severity").annotate(count=Count("id")).order_by("-count")
    )
    top_wallets = list(
        events.filter(wallet_monitor__isnull=False)
        .values("wallet_monitor__name", "wallet_monitor__address")
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
    )
    top_contract_events = list(
        events.filter(contract_monitor__isnull=False)
        .values("contract_monitor__name", "event_signature")
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
    )
    webhook_trend = list(
        deliveries.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(
            total=Count("id"),
            ok=Count("id", filter=Q(status=WebhookDelivery.Status.SUCCESS)),
            failed=Count("id", filter=Q(status__in=["retrying", "exhausted"])),
        )
        .order_by("date")
    )

    def stringify_dates(rows: list[dict]) -> list[dict]:
        return [{**row, "date": str(row["date"])} for row in rows if "date" in row] or rows

    return Response(
        {
            "days": days,
            "events_by_chain": stringify_dates(events_by_chain),
            "events_over_time": stringify_dates(events_over_time),
            "alerts_by_severity": alerts_by_severity,
            "top_wallets": top_wallets,
            "top_contract_events": top_contract_events,
            "webhook_trend": stringify_dates(webhook_trend),
        }
    )


class ContactView(APIView):
    """Public contact form → email to platform operators."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact"

    @extend_schema(operation_id="contact_submit", request=dict, responses={200: dict})
    def post(self, request):
        name = str(request.data.get("name", "")).strip()[:120]
        email = str(request.data.get("email", "")).strip()[:254]
        subject = str(request.data.get("subject", "")).strip()[:180]
        message = str(request.data.get("message", "")).strip()[:5000]
        if not email or not message:
            return Response(
                {"error": {"code": "validation_error", "message": "Email and message are required.", "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.notifications.emails import send_platform_alert

        send_platform_alert(
            subject=f"[ChainSentinel Contact] {subject or 'New message'}",
            template="contact_message",
            context={"name": name, "email": email, "subject": subject, "message": message},
        )
        return Response({"detail": "Thanks — we received your message and will reply by email."})
