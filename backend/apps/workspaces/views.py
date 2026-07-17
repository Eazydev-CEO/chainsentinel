from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsRealUser
from apps.api.permissions import WorkspaceAccessPermission
from apps.api.workspace import resolve_workspace
from apps.audit.services import record_audit

from . import services
from .models import Workspace, WorkspaceInvitation, WorkspaceMember, WorkspaceRole
from .serializers import (
    AcceptInviteSerializer,
    InvitationSerializer,
    InviteCreateSerializer,
    WorkspaceCreateSerializer,
    WorkspaceMemberSerializer,
    WorkspaceSerializer,
)


class WorkspaceViewSet(viewsets.ModelViewSet):
    """Workspaces the requesting user belongs to."""

    permission_classes = [IsAuthenticated, IsRealUser]
    serializer_class = WorkspaceSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (
            Workspace.objects.filter(members__user=self.request.user)
            .annotate(member_count=Count("members", distinct=True))
            .order_by("name")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context["roles"] = dict(
                WorkspaceMember.objects.filter(user=self.request.user).values_list(
                    "workspace_id", "role"
                )
            )
        return context

    def create(self, request, *args, **kwargs):
        serializer = WorkspaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = services.create_workspace(
            name=serializer.validated_data["name"], owner=request.user
        )
        record_audit(request=request, action="workspace.created", target=workspace, workspace=workspace)
        data = WorkspaceSerializer(workspace, context={"roles": {workspace.pk: WorkspaceRole.OWNER}}).data
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        workspace = self.get_object()
        role = services.get_role(request.user, workspace)
        if role != WorkspaceRole.OWNER:
            return _forbidden("Only the workspace owner can update workspace settings.")
        name = (request.data.get("name") or "").strip()
        if name:
            workspace.name = name[:100]
            workspace.save(update_fields=["name", "updated_at"])
            record_audit(request=request, action="workspace.updated", target=workspace, workspace=workspace)
        return Response(self.get_serializer(workspace).data)

    partial_update = update

    def destroy(self, request, *args, **kwargs):
        workspace = self.get_object()
        role = services.get_role(request.user, workspace)
        if role != WorkspaceRole.OWNER:
            return _forbidden("Only the workspace owner can delete the workspace.")
        record_audit(
            request=request,
            action="workspace.deleted",
            workspace=None,
            metadata={"workspace_id": workspace.pk, "name": workspace.name},
        )
        workspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=InviteCreateSerializer, responses={201: InvitationSerializer})
    @action(detail=True, methods=["post"])
    def invite(self, request, pk=None):
        workspace = self.get_object()
        role = services.get_role(request.user, workspace)
        if role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return _forbidden("Only owners and admins can invite members.")
        if not request.user.is_email_verified:
            return _forbidden("Verify your email address before inviting members.")

        serializer = InviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        invite_role = serializer.validated_data["role"]

        # Admins cannot mint other admins — only the owner can.
        if role == WorkspaceRole.ADMIN and invite_role == WorkspaceRole.ADMIN:
            return _forbidden("Only the workspace owner can invite admins.")
        if WorkspaceMember.objects.filter(workspace=workspace, user__email__iexact=email).exists():
            return Response(
                {"error": {"code": "already_member", "message": "That user is already a member.", "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation = services.invite_member(
            workspace=workspace, email=email, role=invite_role, invited_by=request.user
        )
        record_audit(
            request=request,
            action="workspace.member_invited",
            target=workspace,
            workspace=workspace,
            metadata={"email": email, "role": invite_role},
        )
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: InvitationSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def invitations(self, request, pk=None):
        workspace = self.get_object()
        role = services.get_role(request.user, workspace)
        if role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return _forbidden("Only owners and admins can view invitations.")
        pending = workspace.invitations.filter(accepted_at__isnull=True, revoked_at__isnull=True)
        return Response(InvitationSerializer(pending, many=True).data)

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"], url_path="invitations/(?P<invitation_id>[0-9]+)/revoke")
    def revoke_invitation(self, request, pk=None, invitation_id=None):
        workspace = self.get_object()
        role = services.get_role(request.user, workspace)
        if role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return _forbidden("Only owners and admins can revoke invitations.")
        invitation = workspace.invitations.filter(pk=invitation_id).first()
        if invitation and invitation.is_pending:
            invitation.revoked_at = timezone.now()
            invitation.save(update_fields=["revoked_at"])
        return Response({"detail": "Invitation revoked."})


class AcceptInviteView(APIView):
    permission_classes = [IsAuthenticated, IsRealUser]

    @extend_schema(request=AcceptInviteSerializer, responses={200: WorkspaceSerializer})
    def post(self, request):
        serializer = AcceptInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            member = services.accept_invitation(
                token=serializer.validated_data["token"], user=request.user
            )
        except services.InvitationError as exc:
            return Response(
                {"error": {"code": "invalid_invitation", "message": str(exc), "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record_audit(
            request=request,
            action="workspace.member_joined",
            target=member.workspace,
            workspace=member.workspace,
        )
        data = WorkspaceSerializer(
            member.workspace, context={"roles": {member.workspace.pk: member.role}}
        ).data
        return Response(data)


class MemberViewSet(viewsets.ModelViewSet):
    """Members of the active workspace (?workspace=<id>)."""

    permission_classes = [IsAuthenticated, IsRealUser, WorkspaceAccessPermission]
    serializer_class = WorkspaceMemberSerializer
    read_role = WorkspaceRole.VIEWER
    # Writes gate on VIEWER so members can remove THEMSELVES (leave); every
    # other mutation is explicitly role-checked inside the handlers below.
    write_role = WorkspaceRole.VIEWER
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        workspace = resolve_workspace(self.request)
        if workspace is None:
            return WorkspaceMember.objects.none()
        return (
            WorkspaceMember.objects.filter(workspace=workspace)
            .select_related("user")
            .order_by("joined_at")
        )

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        member = self.get_object()
        workspace = member.workspace
        actor_role = services.get_role(request.user, workspace)

        if actor_role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return _forbidden("Only owners and admins can change member roles.")
        if member.role == WorkspaceRole.OWNER:
            return _forbidden("The owner's role cannot be changed here.")
        if actor_role == WorkspaceRole.ADMIN and member.role == WorkspaceRole.ADMIN:
            return _forbidden("Admins cannot modify other admins.")

        serializer = self.get_serializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data.get("role", member.role)
        if actor_role == WorkspaceRole.ADMIN and new_role == WorkspaceRole.ADMIN:
            return _forbidden("Only the workspace owner can promote members to admin.")
        serializer.save()
        record_audit(
            request=request,
            action="workspace.member_role_changed",
            target=workspace,
            workspace=workspace,
            metadata={"member": member.user.email, "role": new_role},
        )
        return Response(serializer.data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        member = self.get_object()
        workspace = member.workspace
        actor_role = services.get_role(request.user, workspace)

        removing_self = member.user_id == request.user.id
        if member.role == WorkspaceRole.OWNER:
            return _forbidden("The workspace owner cannot be removed.")
        if not removing_self:
            if actor_role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
                return _forbidden("Only owners and admins can remove members.")
            if actor_role == WorkspaceRole.ADMIN and member.role == WorkspaceRole.ADMIN:
                return _forbidden("Admins cannot remove other admins.")

        record_audit(
            request=request,
            action="workspace.member_removed",
            target=workspace,
            workspace=workspace,
            metadata={"member": member.user.email, "left_voluntarily": removing_self},
        )
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _forbidden(message: str) -> Response:
    return Response(
        {"error": {"code": "forbidden", "message": message, "details": {}}},
        status=status.HTTP_403_FORBIDDEN,
    )
