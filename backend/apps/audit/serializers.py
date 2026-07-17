from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "action",
            "actor_label",
            "target_type",
            "target_id",
            "target_label",
            "metadata",
            "ip_address",
            "created_at",
        ]
