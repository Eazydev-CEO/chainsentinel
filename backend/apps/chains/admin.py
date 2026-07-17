from django.contrib import admin

from .models import Chain, RpcProvider, RpcProviderHealthLog


class RpcProviderInline(admin.TabularInline):
    model = RpcProvider
    extra = 0
    fields = ["name", "priority", "is_active", "health_status", "consecutive_failures", "last_success_at"]
    readonly_fields = ["health_status", "consecutive_failures", "last_success_at"]


@admin.register(Chain)
class ChainAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "chain_id",
        "native_symbol",
        "is_testnet",
        "is_active",
        "required_confirmations",
        "block_time_seconds",
    ]
    list_filter = ["is_testnet", "is_active"]
    search_fields = ["name", "slug"]
    inlines = [RpcProviderInline]
    actions = ["activate_chains", "deactivate_chains"]

    @admin.action(description="Activate selected chains")
    def activate_chains(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} chain(s).")

    @admin.action(description="Deactivate selected chains (stops polling)")
    def deactivate_chains(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} chain(s).")


@admin.register(RpcProvider)
class RpcProviderAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "chain",
        "priority",
        "is_active",
        "health_status",
        "consecutive_failures",
        "last_latency_ms",
        "last_success_at",
        "last_failure_reason",
    ]
    list_filter = ["chain", "is_active", "health_status"]
    search_fields = ["name", "chain__name"]
    actions = ["disable_providers", "enable_providers", "reset_health"]

    @admin.action(description="Disable selected providers (failing)")
    def disable_providers(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Disabled {updated} provider(s). Failover will skip them.")

    @admin.action(description="Enable selected providers")
    def enable_providers(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Enabled {updated} provider(s).")

    @admin.action(description="Reset health counters")
    def reset_health(self, request, queryset):
        updated = queryset.update(
            consecutive_failures=0,
            health_status=RpcProvider.HealthStatus.UNKNOWN,
            last_failure_reason="",
        )
        self.message_user(request, f"Reset health on {updated} provider(s).")


@admin.register(RpcProviderHealthLog)
class RpcProviderHealthLogAdmin(admin.ModelAdmin):
    list_display = ["provider", "checked_at", "ok", "latency_ms", "block_number", "error"]
    list_filter = ["ok", "provider__chain"]
    date_hierarchy = "checked_at"
    readonly_fields = [f.name for f in RpcProviderHealthLog._meta.fields]

    def has_add_permission(self, request):
        return False
