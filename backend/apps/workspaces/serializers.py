from rest_framework import serializers

from .models import Workspace, WorkspaceInvitation, WorkspaceMember, WorkspaceRole


class WorkspaceSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Workspace
        fields = [
            "id",
            "name",
            "slug",
            "plan",
            "role",
            "member_count",
            "suspended_at",
            "created_at",
        ]
        read_only_fields = ["id", "slug", "plan", "suspended_at", "created_at"]

    def get_role(self, obj: Workspace) -> str | None:
        roles = self.context.get("roles") or {}
        return roles.get(obj.pk)


class WorkspaceCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    name = serializers.CharField(source="user.full_name", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ["id", "user_id", "email", "name", "role", "joined_at"]
        read_only_fields = ["id", "user_id", "email", "name", "joined_at"]

    def validate_role(self, value: str) -> str:
        if value == WorkspaceRole.OWNER:
            raise serializers.ValidationError(
                "Ownership is transferred via the workspace settings, not the member role."
            )
        return value


class InvitationSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True, default=None)
    is_pending = serializers.BooleanField(read_only=True)

    class Meta:
        model = WorkspaceInvitation
        fields = [
            "id",
            "email",
            "role",
            "invited_by_email",
            "created_at",
            "expires_at",
            "accepted_at",
            "revoked_at",
            "is_pending",
        ]
        read_only_fields = fields


class InviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[c for c in WorkspaceRole.choices if c[0] != WorkspaceRole.OWNER]
    )


class AcceptInviteSerializer(serializers.Serializer):
    token = serializers.CharField()
