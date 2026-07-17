import json

from rest_framework import serializers

from apps.chains.models import Chain

from . import abi as abi_tools
from .constants import Direction, MonitorEventCategory, Severity
from .models import ContractAbi, ContractMonitor, EventSubscription, MonitorCsvImport, WalletMonitor
from .validators import normalize_evm_address


class TagsField(serializers.ListField):
    child = serializers.CharField(max_length=40)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        cleaned = sorted({t.strip().lower() for t in value if t.strip()})
        if len(cleaned) > 20:
            raise serializers.ValidationError("At most 20 tags.")
        return cleaned


class WalletMonitorSerializer(serializers.ModelSerializer):
    chain = serializers.SlugRelatedField(slug_field="slug", queryset=Chain.objects.all())
    chain_name = serializers.CharField(source="chain.name", read_only=True)
    tags = TagsField(required=False, default=list)
    event_types = serializers.ListField(
        child=serializers.ChoiceField(choices=MonitorEventCategory.choices), allow_empty=False
    )
    min_value_wei = serializers.DecimalField(
        max_digits=78, decimal_places=0, required=False, allow_null=True, min_value=0
    )
    large_tx_threshold_wei = serializers.DecimalField(
        max_digits=78, decimal_places=0, required=False, allow_null=True, min_value=0
    )
    required_confirmations = serializers.SerializerMethodField()

    class Meta:
        model = WalletMonitor
        fields = [
            "id",
            "name",
            "address",
            "chain",
            "chain_name",
            "direction",
            "event_types",
            "token_contract",
            "min_value_wei",
            "large_tx_threshold_wei",
            "confirmations_override",
            "required_confirmations",
            "severity",
            "is_active",
            "tags",
            "notes",
            "last_processed_block",
            "last_event_at",
            "error_count",
            "last_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "chain_name",
            "last_processed_block",
            "last_event_at",
            "error_count",
            "last_error",
            "created_at",
            "updated_at",
        ]

    def get_required_confirmations(self, obj) -> int:
        return obj.required_confirmations()

    def validate_address(self, value: str) -> str:
        return normalize_evm_address(value)

    def validate_token_contract(self, value: str) -> str:
        if not value:
            return ""
        return normalize_evm_address(value)

    def validate_chain(self, value: Chain) -> Chain:
        if not value.is_active:
            raise serializers.ValidationError(
                f"Chain '{value.slug}' is not active on this platform."
            )
        return value

    def validate_event_types(self, value: list[str]) -> list[str]:
        return sorted(set(value))

    def validate(self, attrs):
        workspace = self.context.get("workspace")
        chain = attrs.get("chain") or (self.instance.chain if self.instance else None)
        address = attrs.get("address") or (self.instance.address if self.instance else None)
        if workspace and chain and address:
            existing = WalletMonitor.objects.filter(
                workspace=workspace, chain=chain, address__iexact=address
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    {"address": "A monitor for this wallet already exists on this chain."}
                )
        return attrs


class ContractAbiSerializer(serializers.ModelSerializer):
    events = serializers.SerializerMethodField()

    class Meta:
        model = ContractAbi
        fields = ["id", "name", "sha256", "events", "created_at"]

    def get_events(self, obj) -> list[dict]:
        try:
            return abi_tools.extract_events(obj.abi)
        except abi_tools.AbiError:
            return []


class ContractMonitorSerializer(serializers.ModelSerializer):
    chain = serializers.SlugRelatedField(slug_field="slug", queryset=Chain.objects.all())
    chain_name = serializers.CharField(source="chain.name", read_only=True)
    tags = TagsField(required=False, default=list)
    abi = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Raw ABI JSON (array). Alternatively pass abi_document_id.",
        style={"base_template": "textarea.html"},
    )
    abi_document_id = serializers.PrimaryKeyRelatedField(
        source="abi_document",
        queryset=ContractAbi.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    abi_document = ContractAbiSerializer(read_only=True)
    selected_events = serializers.ListField(child=serializers.CharField(max_length=120), allow_empty=False)
    available_events = serializers.SerializerMethodField()
    required_confirmations = serializers.SerializerMethodField()

    class Meta:
        model = ContractMonitor
        fields = [
            "id",
            "name",
            "label",
            "address",
            "chain",
            "chain_name",
            "abi",
            "abi_document_id",
            "abi_document",
            "selected_events",
            "available_events",
            "topic_filters",
            "confirmations_override",
            "required_confirmations",
            "severity",
            "is_active",
            "tags",
            "notes",
            "last_processed_block",
            "last_event_at",
            "error_count",
            "last_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "chain_name",
            "abi_document",
            "available_events",
            "last_processed_block",
            "last_event_at",
            "error_count",
            "last_error",
            "created_at",
            "updated_at",
        ]

    def get_available_events(self, obj) -> list[dict]:
        if obj.abi_document_id and obj.abi_document:
            try:
                return abi_tools.extract_events(obj.abi_document.abi)
            except abi_tools.AbiError:
                return []
        return []

    def get_required_confirmations(self, obj) -> int:
        return obj.required_confirmations()

    def validate_address(self, value: str) -> str:
        return normalize_evm_address(value)

    def validate_chain(self, value: Chain) -> Chain:
        if not value.is_active:
            raise serializers.ValidationError(
                f"Chain '{value.slug}' is not active on this platform."
            )
        return value

    def validate(self, attrs):
        workspace = self.context.get("workspace")

        # Resolve the ABI: raw JSON beats document reference.
        raw_abi = attrs.pop("abi", "") or ""
        abi_document = attrs.get("abi_document") or (
            self.instance.abi_document if self.instance else None
        )
        if raw_abi.strip():
            try:
                parsed = abi_tools.parse_abi(raw_abi)
            except abi_tools.AbiError as exc:
                raise serializers.ValidationError({"abi": str(exc)})
            digest = abi_tools.abi_sha256(parsed)
            abi_document, _ = ContractAbi.objects.get_or_create(
                workspace=workspace,
                sha256=digest,
                defaults={
                    "abi": parsed,
                    "name": attrs.get("name") or (self.instance.name if self.instance else "ABI"),
                    "created_by": self.context.get("acting_user"),
                },
            )
        if abi_document is None:
            raise serializers.ValidationError(
                {"abi": "Provide an ABI JSON document (or abi_document_id)."}
            )
        if abi_document.workspace_id != workspace.pk:
            raise serializers.ValidationError({"abi_document_id": "Unknown ABI document."})
        attrs["abi_document"] = abi_document

        # Selected events must exist in the ABI.
        available = {e["name"]: e for e in abi_tools.extract_events(abi_document.abi)}
        if not available:
            raise serializers.ValidationError({"abi": "This ABI defines no events to monitor."})
        selected = attrs.get("selected_events") or (
            self.instance.selected_events if self.instance else []
        )
        unknown = [name for name in selected if name not in available]
        if unknown:
            raise serializers.ValidationError(
                {"selected_events": f"Events not present in ABI: {', '.join(unknown)}."}
            )

        # Topic filters: only on indexed params of selected events.
        topic_filters = attrs.get("topic_filters")
        if topic_filters is None:
            topic_filters = self.instance.topic_filters if self.instance else {}
        if not isinstance(topic_filters, dict):
            raise serializers.ValidationError({"topic_filters": "Must be an object."})
        cleaned_filters: dict = {}
        for event_name, filters in topic_filters.items():
            if event_name not in selected:
                continue  # drop filters for unselected events
            if not isinstance(filters, dict):
                raise serializers.ValidationError(
                    {"topic_filters": f"Filters for '{event_name}' must be an object."}
                )
            indexed = {
                i["name"]: i for i in available[event_name]["inputs"] if i["indexed"]
            }
            entry: dict = {}
            for param, value in filters.items():
                if param not in indexed:
                    raise serializers.ValidationError(
                        {
                            "topic_filters": f"'{param}' is not an indexed parameter of "
                            f"{event_name}."
                        }
                    )
                if indexed[param]["type"] == "address":
                    entry[param] = normalize_evm_address(str(value))
                else:
                    entry[param] = str(value)
            if entry:
                cleaned_filters[event_name] = entry
        attrs["topic_filters"] = cleaned_filters

        # Duplicate monitor check.
        chain = attrs.get("chain") or (self.instance.chain if self.instance else None)
        address = attrs.get("address") or (self.instance.address if self.instance else None)
        if workspace and chain and address:
            existing = ContractMonitor.objects.filter(
                workspace=workspace, chain=chain, address__iexact=address
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    {"address": "A monitor for this contract already exists on this chain."}
                )
        return attrs


class ParseAbiSerializer(serializers.Serializer):
    abi = serializers.CharField()

    def validate(self, attrs):
        try:
            parsed = abi_tools.parse_abi(attrs["abi"])
        except abi_tools.AbiError as exc:
            raise serializers.ValidationError({"abi": str(exc)})
        attrs["parsed"] = parsed
        attrs["events"] = abi_tools.extract_events(parsed)
        return attrs


class MonitorCsvImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitorCsvImport
        fields = [
            "id",
            "filename",
            "total_rows",
            "created_count",
            "failed_count",
            "report",
            "created_at",
        ]


class EventSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventSubscription
        fields = ["id", "event_name", "signature", "topic0", "indexed_filters", "is_active"]
