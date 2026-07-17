"""Workspace business logic."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.notifications.emails import send_templated_email

from .models import Workspace, WorkspaceInvitation, WorkspaceMember, WorkspaceRole


@transaction.atomic
def create_workspace(*, name: str, owner) -> Workspace:
    workspace = Workspace.objects.create(name=name, slug=Workspace.unique_slug(name), owner=owner)
    WorkspaceMember.objects.create(workspace=workspace, user=owner, role=WorkspaceRole.OWNER)
    return workspace


def get_role(user, workspace: Workspace) -> str | None:
    member = WorkspaceMember.objects.filter(workspace=workspace, user=user).first()
    return member.role if member else None


@transaction.atomic
def invite_member(*, workspace: Workspace, email: str, role: str, invited_by) -> WorkspaceInvitation:
    email = email.lower().strip()
    # Refresh any previous pending invite for the same address.
    WorkspaceInvitation.objects.filter(
        workspace=workspace, email=email, accepted_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=timezone.now())

    invitation = WorkspaceInvitation.objects.create(
        workspace=workspace,
        email=email,
        role=role,
        invited_by=invited_by,
        expires_at=timezone.now() + timedelta(seconds=settings.INVITATION_MAX_AGE),
    )
    link = f"{settings.FRONTEND_URL}/accept-invite?token={invitation.token}"
    send_templated_email(
        to=[email],
        subject=f"You're invited to {workspace.name} on ChainSentinel",
        template="workspace_invite",
        context={
            "workspace": workspace,
            "role": role,
            "link": link,
            "invited_by": getattr(invited_by, "email", "a workspace admin"),
        },
    )
    return invitation


class InvitationError(Exception):
    pass


@transaction.atomic
def accept_invitation(*, token: str, user) -> WorkspaceMember:
    invitation = WorkspaceInvitation.objects.select_related("workspace").filter(token=token).first()
    if invitation is None or not invitation.is_pending:
        raise InvitationError("This invitation is invalid or has expired.")
    if invitation.email.lower() != user.email.lower():
        raise InvitationError("This invitation was sent to a different email address.")

    member, created = WorkspaceMember.objects.get_or_create(
        workspace=invitation.workspace,
        user=user,
        defaults={"role": invitation.role, "invited_by": invitation.invited_by},
    )
    if not created:
        raise InvitationError("You are already a member of this workspace.")

    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    return member
