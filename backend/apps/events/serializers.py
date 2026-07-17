from rest_framework import serializers

from .models import BlockchainEvent


class BlockchainEventListSerializer(serializers.ModelSerializer):
    chain_slug = serializers.CharField(source="chain.slug", read_only=True)
    chain_name = serializers.CharField(source="chain.name", read_only=True)
    monitor_name = serializers.SerializerMethodField()
    monitor_kind = serializers.SerializerMethodField()
    amount_wei = serializers.SerializerMethodField()

    class Meta:
        model = BlockchainEvent
        fields = [
            "id",
            "event_type",
            "status",
            "severity",
            "is_large",
            "chain_slug",
            "chain_name",
            "monitor_name",
            "monitor_kind",
            "block_number",
            "tx_hash",
            "log_index",
            "from_address",
            "to_address",
            "spender_address",
            "token_address",
            "token_symbol",
            "token_decimals",
            "token_id",
            "amount_wei",
            "occurred_at",
            "created_at",
        ]

    def get_monitor_name(self, obj) -> str:
        monitor = obj.monitor
        return monitor.name if monitor else ""

    def get_monitor_kind(self, obj) -> str:
        return "wallet" if obj.wallet_monitor_id else "contract"

    def get_amount_wei(self, obj) -> str | None:
        return str(obj.amount_wei) if obj.amount_wei is not None else None


class BlockchainEventDetailSerializer(BlockchainEventListSerializer):
    explorer_tx_url = serializers.SerializerMethodField()
    confirmations_required = serializers.IntegerField(read_only=True)
    current_confirmations = serializers.SerializerMethodField()
    related_alerts = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()
    wallet_monitor_id = serializers.IntegerField(read_only=True)
    contract_monitor_id = serializers.IntegerField(read_only=True)

    class Meta(BlockchainEventListSerializer.Meta):
        fields = BlockchainEventListSerializer.Meta.fields + [
            "block_hash",
            "tx_index",
            "contract_address",
            "event_signature",
            "topic0",
            "decoded",
            "raw",
            "decode_error",
            "confirmations_required",
            "current_confirmations",
            "confirmed_at",
            "reverted_at",
            "explorer_tx_url",
            "wallet_monitor_id",
            "contract_monitor_id",
            "related_alerts",
            "timeline",
        ]

    def get_explorer_tx_url(self, obj) -> str:
        return obj.chain.explorer_tx_url(obj.tx_hash)

    def get_current_confirmations(self, obj) -> int | None:
        checkpoint = getattr(obj.chain, "checkpoint", None)
        if checkpoint is None or not obj.block_number:
            return None
        return max(checkpoint.last_processed_block - obj.block_number + 1, 0)

    def get_related_alerts(self, obj) -> list[dict]:
        return [
            {
                "id": alert.pk,
                "title": alert.title,
                "severity": alert.severity,
                "status": alert.status,
                "created_at": alert.created_at,
            }
            for alert in obj.alerts.all()[:10]
        ]

    def get_timeline(self, obj) -> list[dict]:
        timeline = [
            {"at": obj.created_at, "label": "Detected", "detail": f"Block #{obj.block_number}"}
        ]
        if obj.confirmed_at:
            timeline.append(
                {
                    "at": obj.confirmed_at,
                    "label": "Confirmed",
                    "detail": f"{obj.confirmations_required} confirmations reached",
                }
            )
        if obj.reverted_at:
            timeline.append(
                {"at": obj.reverted_at, "label": "Reverted", "detail": "Chain reorganization"}
            )
        for alert in obj.alerts.all()[:10]:
            timeline.append(
                {"at": alert.created_at, "label": "Alert triggered", "detail": alert.title}
            )
        timeline.sort(key=lambda item: item["at"])
        return timeline
