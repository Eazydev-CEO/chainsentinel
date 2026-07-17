from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Chain, RpcProvider
from .serializers import ChainSerializer, ProviderHealthSerializer


class ChainViewSet(viewsets.ReadOnlyModelViewSet):
    """Supported chains (read-only for all authenticated principals)."""

    queryset = Chain.objects.all().order_by("is_testnet", "name")
    serializer_class = ChainSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["is_testnet", "is_active"]
    search_fields = ["name", "slug"]
    pagination_class = None


class ProviderHealthViewSet(viewsets.ReadOnlyModelViewSet):
    """RPC provider health. Endpoint URLs are never exposed here."""

    queryset = RpcProvider.objects.select_related("chain").order_by("chain__name", "priority")
    serializer_class = ProviderHealthSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["chain__slug", "health_status", "is_active"]
    pagination_class = None
