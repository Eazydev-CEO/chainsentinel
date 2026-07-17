"""Fan-out of workspace notices to members (in-app + email, pref-aware)."""
import logging

from apps.monitors.constants import SEVERITY_ORDER, Severity

from .emails import send_platform_alert, send_templated_email  # noqa: F401 (re-export)
from .models import Notification, NotificationPreference

logger = logging.getLogger("chainsentinel.notifications")


def _severity_at_least(severity: str, minimum: str) -> bool:
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(minimum, 0)


def notify_workspace(
    *,
    workspace,
    type: str,
    severity: str,
    title: str,
    body: str = "",
    link: str = "",
    alert=None,
    in_app: bool = True,
    send_email: bool = False,
    email_template: str | None = None,
    email_context: dict | None = None,
    email_pref_field: str | None = None,
) -> int:
    """Create per-member notifications and (optionally) emails.

    Email gating:
      * `email_pref_field` set → that boolean preference decides (webhook/provider notices)
      * otherwise → `send_email` requests it, member's min_severity_email filters it;
        CRITICAL alerts additionally honour the `email_critical_alerts` opt-in even
        when the rule didn't request email.
    """
    members = workspace.members.select_related("user").filter(user__is_active=True)
    email_recipients: list[str] = []
    created = 0

    for member in members:
        prefs = NotificationPreference.for_user(member.user)

        if in_app and _severity_at_least(severity, prefs.min_severity_in_app):
            Notification.objects.create(
                user=member.user,
                workspace=workspace,
                type=type,
                severity=severity,
                title=title[:255],
                body=body,
                link=link,
                alert=alert,
            )
            created += 1

        if not member.user.is_email_verified:
            continue

        wants_email = False
        if email_pref_field:
            wants_email = bool(getattr(prefs, email_pref_field, False))
        else:
            if send_email and _severity_at_least(severity, prefs.min_severity_email):
                wants_email = True
            elif (
                severity == Severity.CRITICAL
                and type == "alert"
                and prefs.email_critical_alerts
            ):
                wants_email = True
        if wants_email:
            email_recipients.append(member.user.email)

    if email_recipients and email_template:
        send_templated_email(
            to=email_recipients,
            subject=f"[ChainSentinel] {title}"[:180],
            template=email_template,
            context={"title": title, "body": body, "link": link, **(email_context or {})},
        )
    return created
