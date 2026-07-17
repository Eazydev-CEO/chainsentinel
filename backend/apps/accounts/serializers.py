from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import ApiKey, ApiKeyScope, User, UserProfile, UserSession


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["company", "job_title", "timezone"]


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "is_email_verified",
            "date_joined",
            "profile",
        ]
        read_only_fields = ["id", "email", "is_email_verified", "date_joined"]


class UserUpdateSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "profile"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        instance = super().update(instance, validated_data)
        if profile_data is not None:
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            for field, value in profile_data.items():
                setattr(profile, field, value)
            profile.save()
        return instance


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    workspace_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")

    def validate_email(self, value: str) -> str:
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value: str) -> str:
        validate_password(value, user=self.context.get("user"))
        return value


class UserSessionSerializer(serializers.ModelSerializer):
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = [
            "id",
            "user_agent",
            "ip_address",
            "created_at",
            "last_seen_at",
            "revoked_at",
            "is_current",
        ]

    def get_is_current(self, obj: UserSession) -> bool:
        return obj.refresh_jti == self.context.get("current_jti")


class ApiKeySerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True, default=None)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = ApiKey
        fields = [
            "id",
            "workspace",
            "name",
            "prefix",
            "scopes",
            "created_by_email",
            "created_at",
            "expires_at",
            "last_used_at",
            "revoked_at",
            "is_valid",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "prefix",
            "created_by_email",
            "created_at",
            "last_used_at",
            "revoked_at",
            "is_valid",
        ]


class ApiKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=ApiKeyScope.choices), allow_empty=False
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_scopes(self, value: list[str]) -> list[str]:
        return sorted(set(value))
