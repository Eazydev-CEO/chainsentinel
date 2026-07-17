from django.contrib import admin
from django.utils import timezone

from .models import Workspace, WorkspaceInvitation, WorkspaceMember


class MemberInline(admin.TabularInline):
    model = WorkspaceMember
    extra = 0
    raw_id_fields = ["user", "invited_by"]


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "owner", "plan", "suspended_at", "created_at"]
    list_filter = ["plan", "suspended_at"]
    search_fields = ["name", "slug", "owner__email"]
    raw_id_fields = ["owner"]
    inlines = [MemberInline]
    actions = ["suspend_workspaces", "unsuspend_workspaces"]

    @admin.action(description="Suspend selected workspaces (abuse)")
    def suspend_workspaces(self, request, queryset):
        updated = queryset.filter(suspended_at__isnull=True).update(
            suspended_at=timezone.now(), suspended_reason="Suspended by platform operations."
        )
        self.message_user(request, f"Suspended {updated} workspace(s). Their monitors stop processing.")

    @admin.action(description="Lift suspension on selected workspaces")
    def unsuspend_workspaces(self, request, queryset):
        updated = queryset.update(suspended_at=None, suspended_reason="")
        self.message_user(request, f"Unsuspended {updated} workspace(s).")


@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(admin.ModelAdmin):
    list_display = ["workspace", "user", "role", "joined_at"]
    list_filter = ["role"]
    search_fields = ["workspace__name", "user__email"]
    raw_id_fields = ["user", "workspace", "invited_by"]


@admin.register(WorkspaceInvitation)
class WorkspaceInvitationAdmin(admin.ModelAdmin):
    list_display = ["workspace", "email", "role", "created_at", "expires_at", "accepted_at", "revoked_at"]
    list_filter = ["role"]
    search_fields = ["workspace__name", "email"]
    readonly_fields = ["token"]
