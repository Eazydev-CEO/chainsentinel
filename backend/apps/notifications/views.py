from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsRealUser

from .models import Notification, NotificationPreference
from .serializers import NotificationPreferenceSerializer, NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """The requesting user's notifications (all workspaces, filterable)."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsRealUser]
    filterset_fields = ["type", "severity", "workspace"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user).select_related("workspace")
        unread = self.request.query_params.get("unread")
        if unread == "true":
            queryset = queryset.filter(read_at__isnull=True)
        return queryset

    @extend_schema(responses={200: {"type": "object", "properties": {"unread": {"type": "integer"}}}})
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
        return Response({"unread": count})

    @extend_schema(request=None, responses={200: NotificationSerializer})
    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)

    @extend_schema(request=None)
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = Notification.objects.filter(user=request.user, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return Response({"marked_read": updated})

    @extend_schema(
        request=NotificationPreferenceSerializer, responses={200: NotificationPreferenceSerializer}
    )
    @action(detail=False, methods=["get", "put"], url_path="preferences")
    def preferences(self, request):
        prefs = NotificationPreference.for_user(request.user)
        if request.method == "PUT":
            serializer = NotificationPreferenceSerializer(prefs, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response(NotificationPreferenceSerializer(prefs).data)
