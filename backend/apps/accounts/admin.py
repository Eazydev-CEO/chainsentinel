from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import ApiKey, User, UserProfile, UserSession


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["email", "full_name", "is_email_verified", "is_active", "is_staff", "date_joined"]
    list_filter = ["is_active", "is_staff", "is_email_verified"]
    search_fields = ["email", "first_name", "last_name"]
    readonly_fields = ["date_joined", "last_login", "email_verified_at"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name")}),
        ("Status", {"fields": ("is_active", "is_email_verified", "email_verified_at")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)

    @admin.display(description="Name")
    def full_name(self, obj):
        return obj.full_name


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "company", "timezone", "updated_at"]
    search_fields = ["user__email", "company"]


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "ip_address", "created_at", "last_seen_at", "revoked_at"]
    list_filter = ["revoked_at"]
    search_fields = ["user__email", "ip_address"]
    readonly_fields = [f.name for f in UserSession._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ["prefix", "name", "workspace", "scopes", "created_by", "last_used_at", "revoked_at"]
    list_filter = ["revoked_at"]
    search_fields = ["prefix", "name", "workspace__name"]
    readonly_fields = ["prefix", "hashed_key", "created_at", "last_used_at"]

    def has_add_permission(self, request):
        return False  # keys must be created via the API so the secret is delivered once
