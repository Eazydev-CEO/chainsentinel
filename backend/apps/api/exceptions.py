"""Consistent API error envelope: {"error": {"code", "message", "details"}}."""
import logging

from rest_framework import exceptions
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("chainsentinel.api")


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception → recorded, then Django's prod-safe 500 page.
        try:
            from apps.audit.services import log_system_error

            log_system_error(
                source="api",
                message=f"Unhandled exception in {context.get('view').__class__.__name__}",
                exc=exc,
            )
        except Exception:  # pragma: no cover — never mask the original error
            logger.exception("Failed to record system error")
        return None

    data = response.data
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        return response  # view already produced the envelope

    if isinstance(exc, exceptions.ValidationError):
        code, message = "validation_error", "Validation failed. Check the details."
        details = data
    elif isinstance(exc, exceptions.Throttled):
        code = "throttled"
        message = "Too many requests. Please slow down."
        details = {"wait_seconds": exc.wait}
    else:
        code = getattr(exc, "default_code", "error") or "error"
        if isinstance(data, dict) and "detail" in data:
            message = str(data["detail"])
            details = {}
        else:
            message = "Request failed."
            details = data if isinstance(data, (dict, list)) else {"detail": str(data)}

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
