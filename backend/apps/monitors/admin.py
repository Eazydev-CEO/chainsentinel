from django.contrib import admin

from .models import ContractAbi, ContractMonitor, EventSubscription, MonitorCsvImport, WalletMonitor


@admin.register(WalletMonitor)
class WalletMonitorAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "address",
        "chain",
        "workspace",
        "direction",
        "severity",
        "is_active",
        "last_event_at",
        "error_count",
    ]
    list_filter = ["chain", "is_active", "severity", "direction"]
    search_fields = ["name", "address", "workspace__name"]
    raw_id_fields = ["workspace", "created_by"]
    actions = ["pause_monitors", "resume_monitors"]

    @admin.action(description="Pause selected monitors (problematic)")
    def pause_monitors(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Paused {updated} monitor(s).")

    @admin.action(description="Resume selected monitors")
    def resume_monitors(self, request, queryset):
        updated = queryset.update(is_active=True, error_count=0, last_error="")
        self.message_user(request, f"Resumed {updated} monitor(s).")


class EventSubscriptionInline(admin.TabularInline):
    model = EventSubscription
    extra = 0
    readonly_fields = ["event_name", "signature", "topic0", "indexed_filters"]


@admin.register(ContractMonitor)
class ContractMonitorAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "address",
        "chain",
        "workspace",
        "severity",
        "is_active",
        "last_event_at",
        "error_count",
    ]
    list_filter = ["chain", "is_active", "severity"]
    search_fields = ["name", "address", "workspace__name"]
    raw_id_fields = ["workspace", "created_by", "abi_document"]
    inlines = [EventSubscriptionInline]
    actions = ["pause_monitors", "resume_monitors"]

    @admin.action(description="Pause selected monitors (problematic)")
    def pause_monitors(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Paused {updated} monitor(s).")

    @admin.action(description="Resume selected monitors")
    def resume_monitors(self, request, queryset):
        updated = queryset.update(is_active=True, error_count=0, last_error="")
        self.message_user(request, f"Resumed {updated} monitor(s).")


@admin.register(ContractAbi)
class ContractAbiAdmin(admin.ModelAdmin):
    list_display = ["name", "workspace", "sha256", "created_at"]
    search_fields = ["name", "sha256", "workspace__name"]
    raw_id_fields = ["workspace", "created_by"]


@admin.register(MonitorCsvImport)
class MonitorCsvImportAdmin(admin.ModelAdmin):
    list_display = ["filename", "workspace", "total_rows", "created_count", "failed_count", "created_at"]
    search_fields = ["filename", "workspace__name"]
    readonly_fields = [f.name for f in MonitorCsvImport._meta.fields]

    def has_add_permission(self, request):
        return False
