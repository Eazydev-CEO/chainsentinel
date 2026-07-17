from rest_framework import serializers

from .models import WEBHOOK_EVENT_TYPE_VALUES, WebhookDelivery, WebhookEndpoint
from .ssrf import WebhookSecurityError, validate_webhook_url


class WebhookEndpointSerializer(serializers.ModelSerializer):
    """The signing secret is intentionally absent — it is returned exactly
    once by create/regenerate responses and never stored in plaintext."""

    class Meta:
        model = WebhookEndpoint
        fields = [
            "id",
            "name",
            "url",
            "enabled",
            "event_types",
            "max_retries",
            "timeout_seconds",
            "last_status",
            "last_success_at",
            "last_failure_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "last_status",
            "last_success_at",
            "last_failure_reason",
            "created_at",
            "updated_at",
        ]

    def validate_url(self, value: str) -> str:
        try:
            # Structural validation at save time (no DNS dependency for tests);
            # full resolution happens again at delivery time.
            validate_webhook_url(value, resolve=False)
        except WebhookSecurityError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate_event_types(self, value: list[str]) -> list[str]:
        if not value:
            raise serializers.ValidationError("Select at least one event type.")
        unknown = [v for v in value if v not in WEBHOOK_EVENT_TYPE_VALUES]
        if unknown:
            raise serializers.ValidationError(f"Unknown event types: {', '.join(unknown)}")
        return sorted(set(value))

    def validate_max_retries(self, value: int) -> int:
        return max(0, min(value, 10))

    def validate_timeout_seconds(self, value: int) -> int:
        return max(1, min(value, 30))


class WebhookDeliverySerializer(serializers.ModelSerializer):
    endpoint_name = serializers.CharField(source="endpoint.name", read_only=True)

    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "endpoint",
            "endpoint_name",
            "event_type",
            "payload",
            "status",
            "attempt_count",
            "max_attempts",
            "response_status",
            "response_time_ms",
            "failure_reason",
            "next_retry_at",
            "delivered_at",
            "replay_of",
            "created_at",
        ]
        read_only_fields = fields
