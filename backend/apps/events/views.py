import django_filters
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.api.permissions import WorkspaceAccessPermission
from apps.api.workspace import resolve_workspace
from apps.workspaces.models import WorkspaceRole

from .models import BlockchainEvent
from .serializers import BlockchainEventDetailSerializer, BlockchainEventListSerializer


class BlockchainEventFilter(django_filters.FilterSet):
    chain = django_filters.CharFilter(field_name="chain__slug")
    wallet_monitor = django_filters.NumberFilter(field_name="wallet_monitor_id")
    contract_monitor = django_filters.NumberFilter(field_name="contract_monitor_id")
    event_type = django_filters.CharFilter(field_name="event_type")
    status = django_filters.CharFilter(field_name="status")
    severity = django_filters.CharFilter(field_name="severity")
    token = django_filters.CharFilter(field_name="token_address", lookup_expr="iexact")
    tx_hash = django_filters.CharFilter(field_name="tx_hash", lookup_expr="iexact")
    block_number = django_filters.NumberFilter(field_name="block_number")
    block_min = django_filters.NumberFilter(field_name="block_number", lookup_expr="gte")
    block_max = django_filters.NumberFilter(field_name="block_number", lookup_expr="lte")
    address = django_filters.CharFilter(method="filter_address")
    is_large = django_filters.BooleanFilter(field_name="is_large")
    date_from = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    date_to = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = BlockchainEvent
        fields = []

    def filter_address(self, queryset, name, value):
        from django.db.models import Q

        return queryset.filter(
            Q(from_address__iexact=value)
            | Q(to_address__iexact=value)
            | Q(spender_address__iexact=value)
            | Q(contract_address__iexact=value)
        )


class BlockchainEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Event explorer. Events are written by the engine, never via the API."""

    permission_classes = [IsAuthenticated, WorkspaceAccessPermission]
    read_role = WorkspaceRole.VIEWER
    filterset_class = BlockchainEventFilter
    search_fields = ["tx_hash", "from_address", "to_address", "token_symbol"]
    ordering_fields = ["block_number", "created_at", "occurred_at"]
    ordering = ["-block_number", "-log_index"]

    def get_queryset(self):
        workspace = resolve_workspace(self.request)
        if workspace is None:
            return BlockchainEvent.objects.none()
        queryset = BlockchainEvent.objects.filter(workspace=workspace).select_related(
            "chain", "wallet_monitor", "contract_monitor"
        )
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("alerts").select_related("chain__checkpoint")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BlockchainEventDetailSerializer
        return BlockchainEventListSerializer
