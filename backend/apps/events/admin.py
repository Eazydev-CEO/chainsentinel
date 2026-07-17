from django.contrib import admin

from .models import BlockchainEvent, BlockCheckpoint, ReorgIncident


@admin.register(BlockCheckpoint)
class BlockCheckpointAdmin(admin.ModelAdmin):
    list_display = ["chain", "last_processed_block", "last_processed_hash", "updated_at"]
    readonly_fields = ["updated_at"]


@admin.register(BlockchainEvent)
class BlockchainEventAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "chain",
        "event_type",
        "status",
        "severity",
        "block_number",
        "short_tx",
        "workspace",
    ]
    list_filter = ["status", "event_type", "severity", "chain"]
    search_fields = ["tx_hash", "from_address", "to_address", "idempotency_key"]
    date_hierarchy = "created_at"
    raw_id_fields = ["workspace", "wallet_monitor", "contract_monitor", "chain"]
    readonly_fields = ["idempotency_key", "created_at"]
    actions = ["retry_alert_processing"]

    @admin.display(description="Tx")
    def short_tx(self, obj):
        return f"{obj.tx_hash[:14]}…"

    @admin.action(description="Retry alert processing for selected events")
    def retry_alert_processing(self, request, queryset):
        from .tasks import reprocess_event_alerts

        count = 0
        for event in queryset.filter(status="confirmed"):
            reprocess_event_alerts.delay(event.pk)
            count += 1
        self.message_user(request, f"Requeued alert evaluation for {count} confirmed event(s).")


@admin.register(ReorgIncident)
class ReorgIncidentAdmin(admin.ModelAdmin):
    list_display = ["detected_at", "chain", "fork_block", "depth", "events_reverted"]
    list_filter = ["chain"]
    readonly_fields = [f.name for f in ReorgIncident._meta.fields]

    def has_add_permission(self, request):
        return False
