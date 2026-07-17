from rest_framework import serializers

from apps.chains.models import Chain
from apps.monitors.constants import ALERTABLE_EVENT_TYPES
from apps.monitors.models import ContractMonitor, WalletMonitor
from apps.monitors.validators import normalize_evm_address
from apps.webhooks.models import WebhookEndpoint

from .models import Alert, AlertNote, AlertRule

VALID_EVENT_TYPES = {value for value, _ in ALERTABLE_EVENT_TYPES}


class AlertRuleSerializer(serializers.ModelSerializer):
    chain = serializers.SlugRelatedField(
        slug_field="slug", queryset=Chain.objects.all(), required=False, allow_null=True
    )
    wallet_monitor = serializers.PrimaryKeyRelatedField(
        queryset=WalletMonitor.objects.all(), required=False, allow_null=True
    )
    contract_monitor = serializers.PrimaryKeyRelatedField(
        queryset=ContractMonitor.objects.all(), required=False, allow_null=True
    )
    webhook = serializers.PrimaryKeyRelatedField(
        queryset=WebhookEndpoint.objects.all(), required=False, allow_null=True
    )
    wallet_monitor_name = serializers.CharField(source="wallet_monitor.name", read_only=True, default=None)
    contract_monitor_name = serializers.CharField(source="contract_monitor.name", read_only=True, default=None)

    class Meta:
        model = AlertRule
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "wallet_monitor",
            "wallet_monitor_name",
            "contract_monitor",
            "contract_monitor_name",
            "chain",
            "event_types",
            "token_address",
            "min_amount_wei",
            "max_amount_wei",
            "from_address",
            "to_address",
            "spender_address",
            "topic0",
            "trigger_on",
            "severity",
            "cooldown_seconds",
            "group_window_seconds",
            "notify_in_app",
            "notify_email",
            "notify_webhook",
            "webhook",
            "telegram_enabled",
            "slack_enabled",
            "last_triggered_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "last_triggered_at", "created_at", "updated_at"]

    def validate_event_types(self, value):
        unknown = [v for v in value if v not in VALID_EVENT_TYPES]
        if unknown:
            raise serializers.ValidationError(f"Unknown event types: {', '.join(unknown)}")
        return sorted(set(value))

    def _validate_optional_address(self, value):
        return normalize_evm_address(value) if value else ""

    def validate_token_address(self, value):
        return self._validate_optional_address(value)

    def validate_from_address(self, value):
        return self._validate_optional_address(value)

    def validate_to_address(self, value):
        return self._validate_optional_address(value)

    def validate_spender_address(self, value):
        return self._validate_optional_address(value)

    def validate_cooldown_seconds(self, value):
        if value > 86400 * 7:
            raise serializers.ValidationError("Cooldown cannot exceed 7 days.")
        return value

    def validate_group_window_seconds(self, value):
        if value > 86400:
            raise serializers.ValidationError("Grouping window cannot exceed 24 hours.")
        return value

    def validate(self, attrs):
        workspace = self.context.get("workspace")
        for field in ("wallet_monitor", "contract_monitor", "webhook"):
            obj = attrs.get(field)
            if obj is not None and obj.workspace_id != workspace.pk:
                raise serializers.ValidationError({field: "Not part of this workspace."})
        min_amount = attrs.get("min_amount_wei")
        max_amount = attrs.get("max_amount_wei")
        if min_amount is not None and max_amount is not None and min_amount > max_amount:
            raise serializers.ValidationError(
                {"max_amount_wei": "Must be greater than the minimum amount."}
            )
        if attrs.get("notify_webhook") and not attrs.get("webhook"):
            # allowed: blank webhook means "all endpoints subscribed to alert.triggered"
            pass
        return attrs


class AlertNoteSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="author.email", read_only=True, default=None)

    class Meta:
        model = AlertNote
        fields = ["id", "body", "author_email", "created_at"]
        read_only_fields = ["id", "author_email", "created_at"]


class AlertSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True, default=None)
    event_id = serializers.IntegerField(read_only=True)
    chain_slug = serializers.CharField(source="event.chain.slug", read_only=True, default=None)
    acknowledged_by_email = serializers.EmailField(source="acknowledged_by.email", read_only=True, default=None)
    resolved_by_email = serializers.EmailField(source="resolved_by.email", read_only=True, default=None)

    class Meta:
        model = Alert
        fields = [
            "id",
            "title",
            "message",
            "severity",
            "status",
            "rule",
            "rule_name",
            "event_id",
            "chain_slug",
            "count",
            "first_seen_at",
            "last_seen_at",
            "acknowledged_by_email",
            "acknowledged_at",
            "resolved_by_email",
            "resolved_at",
            "created_at",
        ]
        read_only_fields = fields


class AlertDetailSerializer(AlertSerializer):
    notes = AlertNoteSerializer(many=True, read_only=True)
    timeline = serializers.SerializerMethodField()

    class Meta(AlertSerializer.Meta):
        fields = AlertSerializer.Meta.fields + ["notes", "timeline"]

    def get_timeline(self, obj) -> list[dict]:
        timeline = [{"at": obj.created_at, "label": "Alert triggered", "detail": obj.title}]
        if obj.count > 1:
            timeline.append(
                {
                    "at": obj.last_seen_at,
                    "label": "Grouped occurrences",
                    "detail": f"{obj.count} matching events folded into this alert",
                }
            )
        if obj.acknowledged_at:
            who = obj.acknowledged_by.email if obj.acknowledged_by else "someone"
            timeline.append(
                {"at": obj.acknowledged_at, "label": "Acknowledged", "detail": f"by {who}"}
            )
        for note in obj.notes.all():
            author = note.author.email if note.author else "unknown"
            timeline.append(
                {"at": note.created_at, "label": "Note added", "detail": f"{author}: {note.body[:120]}"}
            )
        if obj.resolved_at:
            who = obj.resolved_by.email if obj.resolved_by else "someone"
            timeline.append({"at": obj.resolved_at, "label": "Resolved", "detail": f"by {who}"})
        timeline.sort(key=lambda item: item["at"])
        return timeline
