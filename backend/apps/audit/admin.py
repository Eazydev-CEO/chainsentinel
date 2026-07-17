from django.contrib import admin

from .models import AuditLog, SystemErrorLog, WorkerJobLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "action", "actor_label", "workspace", "target_type", "target_label", "ip_address"]
    list_filter = ["action"]
    search_fields = ["action", "actor_label", "target_label", "ip_address"]
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SystemErrorLog)
class SystemErrorLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "level", "source", "short_message"]
    list_filter = ["level", "source"]
    search_fields = ["message"]
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in SystemErrorLog._meta.fields]

    @admin.display(description="Message")
    def short_message(self, obj):
        return obj.message[:120]

    def has_add_permission(self, request):
        return False


@admin.register(WorkerJobLog)
class WorkerJobLogAdmin(admin.ModelAdmin):
    list_display = ["started_at", "task_name", "chain", "status", "duration_ms"]
    list_filter = ["status", "task_name"]
    search_fields = ["task_name", "task_id"]
    date_hierarchy = "started_at"
    readonly_fields = [f.name for f in WorkerJobLog._meta.fields]

    def has_add_permission(self, request):
        return False
