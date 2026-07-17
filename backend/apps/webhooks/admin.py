from django.contrib import admin

from .models import WebhookDelivery, WebhookEndpoint


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "workspace",
        "url",
        "enabled",
        "last_status",
        "last_success_at",
        "last_failure_reason",
    ]
    list_filter = ["enabled", "last_status"]
    search_fields = ["name", "url", "workspace__name"]
    raw_id_fields = ["workspace", "created_by"]
    readonly_fields = ["secret_encrypted", "last_status", "last_success_at", "last_failure_reason"]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "endpoint",
        "event_type",
        "status",
        "attempt_count",
        "response_status",
        "response_time_ms",
        "failure_reason",
        "next_retry_at",
    ]
    list_filter = ["status", "event_type"]
    search_fields = ["idempotency_key", "endpoint__name", "workspace__name"]
    date_hierarchy = "created_at"
    raw_id_fields = ["endpoint", "workspace", "replay_of"]
    readonly_fields = ["idempotency_key", "payload", "created_at"]
    actions = ["retry_deliveries"]

    @admin.action(description="Retry selected failed/exhausted deliveries")
    def retry_deliveries(self, request, queryset):
        from .tasks import deliver_webhook

        count = 0
        for delivery in queryset.exclude(status=WebhookDelivery.Status.SUCCESS):
            if delivery.status == WebhookDelivery.Status.EXHAUSTED:
                delivery.attempt_count = 0
                delivery.status = WebhookDelivery.Status.PENDING
                delivery.save(update_fields=["attempt_count", "status"])
            deliver_webhook.delay(delivery.pk)
            count += 1
        self.message_user(request, f"Requeued {count} delivery(ies).")
