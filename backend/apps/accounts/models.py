import hashlib
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """ChainSentinel user. Email is the login identifier."""

    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "cs_user"

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def mark_email_verified(self) -> None:
        if not self.is_email_verified:
            self.is_email_verified = True
            self.email_verified_at = timezone.now()
            self.save(update_fields=["is_email_verified", "email_verified_at"])


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    company = models.CharField(max_length=150, blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cs_user_profile"

    def __str__(self) -> str:
        return f"Profile<{self.user.email}>"


class UserSession(models.Model):
    """A device/browser session backed by a refresh-token family (jti)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    refresh_jti = models.CharField(max_length=64, unique=True)
    user_agent = models.CharField(max_length=512, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "cs_user_session"
        ordering = ["-last_seen_at"]
        indexes = [models.Index(fields=["user", "revoked_at"])]

    def __str__(self) -> str:
        return f"Session<{self.user.email} {self.refresh_jti[:8]}>"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])


class ApiKeyScope(models.TextChoices):
    READ = "read", "Read"
    WRITE = "write", "Write"


class ApiKey(models.Model):
    """Workspace-scoped API key. The full key is shown exactly once at creation.

    Format: ``cs_<prefix>_<secret>``. Only a SHA-256 hash is stored.
    """

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="api_keys"
    )
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=12, unique=True, db_index=True)
    hashed_key = models.CharField(max_length=64)
    scopes = models.JSONField(default=list)  # list[str] of ApiKeyScope values
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="api_keys"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "cs_api_key"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["workspace", "revoked_at"])]

    def __str__(self) -> str:
        return f"ApiKey<{self.workspace_id}:{self.prefix}>"

    # -- key material -------------------------------------------------------
    @staticmethod
    def generate() -> tuple[str, str, str]:
        """Return (full_key, prefix, sha256_hash)."""
        prefix = secrets.token_hex(4)  # 8 chars
        secret = secrets.token_urlsafe(32)
        full_key = f"cs_{prefix}_{secret}"
        return full_key, prefix, hashlib.sha256(full_key.encode()).hexdigest()

    @staticmethod
    def hash_key(full_key: str) -> str:
        return hashlib.sha256(full_key.encode()).hexdigest()

    @property
    def is_valid(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])

    def mark_used(self) -> None:
        # Throttled write: at most once per minute to avoid hot-row churn.
        now = timezone.now()
        if self.last_used_at is None or (now - self.last_used_at).total_seconds() > 60:
            self.last_used_at = now
            self.save(update_fields=["last_used_at"])


class ApiKeyPrincipal:
    """Request 'user' when authenticated via API key (not a DB row)."""

    is_active = True
    is_staff = False
    is_superuser = False
    is_anonymous = False
    is_authenticated = True

    def __init__(self, api_key: ApiKey):
        self.api_key = api_key
        self.workspace = api_key.workspace
        self.pk = None
        self.id = None
        self.email = f"api-key:{api_key.prefix}"

    def __str__(self) -> str:
        return self.email
