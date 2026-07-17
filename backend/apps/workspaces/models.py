import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class WorkspaceRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    ANALYST = "analyst", "Analyst"
    VIEWER = "viewer", "Viewer"


ROLE_ORDER: dict[str, int] = {
    WorkspaceRole.VIEWER: 0,
    WorkspaceRole.ANALYST: 1,
    WorkspaceRole.ADMIN: 2,
    WorkspaceRole.OWNER: 3,
}


def role_at_least(role: str, minimum: str) -> bool:
    return ROLE_ORDER.get(role, -1) >= ROLE_ORDER.get(minimum, 99)


class Workspace(models.Model):
    """Tenant boundary. Every monitoring object belongs to exactly one workspace."""

    class Plan(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro (placeholder)"
        ENTERPRISE = "enterprise", "Enterprise (placeholder)"

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_workspaces"
    )
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cs_workspace"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_suspended(self) -> bool:
        return self.suspended_at is not None

    @staticmethod
    def unique_slug(name: str) -> str:
        base = slugify(name)[:100] or "workspace"
        slug = base
        while Workspace.objects.filter(slug=slug).exists():
            slug = f"{base}-{secrets.token_hex(3)}"
        return slug


class WorkspaceMember(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspace_memberships"
    )
    role = models.CharField(max_length=20, choices=WorkspaceRole.choices, default=WorkspaceRole.VIEWER)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cs_workspace_member"
        constraints = [
            models.UniqueConstraint(fields=["workspace", "user"], name="uniq_workspace_user")
        ]
        indexes = [models.Index(fields=["user", "workspace"])]

    def __str__(self) -> str:
        return f"{self.user} @ {self.workspace} ({self.role})"


class WorkspaceInvitation(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=WorkspaceRole.choices, default=WorkspaceRole.VIEWER)
    token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "cs_workspace_invitation"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["workspace", "email"])]

    def __str__(self) -> str:
        return f"Invite<{self.email} → {self.workspace} as {self.role}>"

    @property
    def is_pending(self) -> bool:
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )
