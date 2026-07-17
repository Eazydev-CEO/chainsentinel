from django.contrib import admin

from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "workspace", "type", "severity", "title", "read_at"]
    list_filter = ["type", "severity"]
    search_fields = ["title", "user__email", "workspace__name"]
    date_hierarchy = "created_at"
    raw_id_fields = ["user", "workspace", "alert"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "min_severity_in_app",
        "min_severity_email",
        "email_critical_alerts",
        "email_daily_summary",
    ]
    search_fields = ["user__email"]
    raw_id_fields = ["user"]
