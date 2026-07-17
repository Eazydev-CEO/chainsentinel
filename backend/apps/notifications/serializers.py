from rest_framework import serializers

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    workspace_name = serializers.CharField(source="workspace.name", read_only=True, default=None)
    alert_id = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "severity",
            "title",
            "body",
            "link",
            "workspace",
            "workspace_name",
            "alert_id",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "min_severity_in_app",
            "min_severity_email",
            "email_critical_alerts",
            "email_failed_webhooks",
            "email_provider_outage",
            "email_daily_summary",
        ]
