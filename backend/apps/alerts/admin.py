from django.contrib import admin

from .models import Alert, AlertNote, AlertRule


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "workspace",
        "is_active",
        "trigger_on",
        "severity",
        "notify_in_app",
        "notify_email",
        "notify_webhook",
        "last_triggered_at",
    ]
    list_filter = ["is_active", "trigger_on", "severity"]
    search_fields = ["name", "workspace__name"]
    raw_id_fields = ["workspace", "wallet_monitor", "contract_monitor", "chain", "webhook", "created_by"]


class AlertNoteInline(admin.TabularInline):
    model = AlertNote
    extra = 0
    readonly_fields = ["author", "body", "created_at"]


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["created_at", "title", "workspace", "severity", "status", "count"]
    list_filter = ["severity", "status"]
    search_fields = ["title", "workspace__name", "dedupe_key"]
    date_hierarchy = "created_at"
    raw_id_fields = ["workspace", "rule", "event", "acknowledged_by", "resolved_by"]
    readonly_fields = ["dedupe_key", "group_key", "created_at"]
    inlines = [AlertNoteInline]
