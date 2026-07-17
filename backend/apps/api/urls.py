"""Versioned API v1 routing."""
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.accounts.views import ApiKeyViewSet
from apps.alerts.views import AlertRuleViewSet, AlertViewSet
from apps.audit.views import AuditLogViewSet
from apps.chains.views import ChainViewSet, ProviderHealthViewSet
from apps.events.views import BlockchainEventViewSet
from apps.monitors.views import ContractMonitorViewSet, WalletMonitorViewSet
from apps.notifications.views import NotificationViewSet
from apps.webhooks.views import WebhookDeliveryViewSet, WebhookEndpointViewSet
from apps.workspaces.views import AcceptInviteView, MemberViewSet, WorkspaceViewSet

from .views import ContactView, analytics_charts, analytics_overview

router = DefaultRouter()
router.register("workspaces", WorkspaceViewSet, basename="workspace")
router.register("members", MemberViewSet, basename="member")
router.register("chains", ChainViewSet, basename="chain")
router.register("provider-health", ProviderHealthViewSet, basename="provider-health")
router.register("wallet-monitors", WalletMonitorViewSet, basename="wallet-monitor")
router.register("contract-monitors", ContractMonitorViewSet, basename="contract-monitor")
router.register("events", BlockchainEventViewSet, basename="event")
router.register("alerts", AlertViewSet, basename="alert")
router.register("alert-rules", AlertRuleViewSet, basename="alert-rule")
router.register("webhooks", WebhookEndpointViewSet, basename="webhook")
router.register("webhook-deliveries", WebhookDeliveryViewSet, basename="webhook-delivery")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("api-keys", ApiKeyViewSet, basename="api-key")
router.register("audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("workspaces/accept-invite/", AcceptInviteView.as_view(), name="accept-invite"),
    path("analytics/overview/", analytics_overview, name="analytics-overview"),
    path("analytics/charts/", analytics_charts, name="analytics-charts"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("", include(router.urls)),
]
