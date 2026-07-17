from rest_framework import serializers

from .models import Chain, RpcProvider


class ChainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chain
        fields = [
            "id",
            "name",
            "slug",
            "chain_id",
            "native_symbol",
            "explorer_url",
            "is_testnet",
            "is_active",
            "required_confirmations",
            "block_time_seconds",
        ]


class ProviderHealthSerializer(serializers.ModelSerializer):
    """Provider health WITHOUT endpoint URLs (those may embed API keys)."""

    chain_slug = serializers.CharField(source="chain.slug", read_only=True)
    chain_name = serializers.CharField(source="chain.name", read_only=True)

    class Meta:
        model = RpcProvider
        fields = [
            "id",
            "name",
            "chain_slug",
            "chain_name",
            "priority",
            "is_active",
            "health_status",
            "consecutive_failures",
            "last_success_at",
            "last_failure_at",
            "last_failure_reason",
            "last_latency_ms",
        ]
