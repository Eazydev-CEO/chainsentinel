"""Audit + operational logging services. Best-effort: never break the caller."""
import logging
import traceback as tb_module

from django.utils import timezone

from .models import AuditLog, SystemErrorLog, WorkerJobLog
from .redaction import redact_sensitive

logger = logging.getLogger("chainsentinel.audit")


def record_audit(
    *,
    request=None,
    action: str,
    target=None,
    workspace=None,
    actor=None,
    metadata: dict | None = None,
) -> None:
    try:
        from apps.accounts.models import ApiKeyPrincipal

        ip = user_agent = None
        if request is not None:
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
            ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
            user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]
            if actor is None:
                request_user = getattr(request, "user", None)
                if isinstance(request_user, ApiKeyPrincipal):
                    actor = request_user.api_key.created_by
                    metadata = {**(metadata or {}), "via_api_key": request_user.api_key.prefix}
                elif getattr(request_user, "is_authenticated", False):
                    actor = request_user

        AuditLog.objects.create(
            workspace=workspace,
            actor=actor if getattr(actor, "pk", None) else None,
            actor_label=getattr(actor, "email", "") or "",
            action=action,
            target_type=target.__class__.__name__ if target is not None else "",
            target_id=str(getattr(target, "pk", "") or ""),
            target_label=str(target)[:255] if target is not None else "",
            metadata=redact_sensitive(metadata or {}),
            ip_address=ip,
            user_agent=user_agent or "",
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to write audit log for action=%s", action)


def log_system_error(
    *, source: str, message: str, level: str = "error", details: dict | None = None, exc=None
) -> None:
    try:
        trace = ""
        if exc is not None:
            trace = "".join(
                tb_module.format_exception(type(exc), exc, exc.__traceback__)
            )[-8000:]
        SystemErrorLog.objects.create(
            source=source,
            level=level,
            message=message[:5000],
            details=redact_sensitive(details or {}),
            traceback=redact_sensitive_text(trace),
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to write system error log: %s", message)


def redact_sensitive_text(text: str) -> str:
    from .redaction import SENSITIVE_PATTERNS

    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class job_log:
    """Context manager recording a worker job run."""

    def __init__(self, task_name: str, task_id: str = "", chain=None, **detail):
        self.entry = WorkerJobLog.objects.create(
            task_name=task_name, task_id=task_id or "", chain=chain, detail=detail
        )

    def __enter__(self):
        return self.entry

    def __exit__(self, exc_type, exc, _tb):
        now = timezone.now()
        self.entry.finished_at = now
        self.entry.duration_ms = int((now - self.entry.started_at).total_seconds() * 1000)
        if exc is not None:
            self.entry.status = WorkerJobLog.Status.FAILED
            self.entry.error = redact_sensitive_text(str(exc))[:4000]
        else:
            self.entry.status = WorkerJobLog.Status.SUCCESS
        self.entry.save(
            update_fields=["finished_at", "duration_ms", "status", "error", "detail"]
        )
        return False  # never swallow
