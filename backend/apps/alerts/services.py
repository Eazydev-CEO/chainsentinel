"""Alert rule evaluation: matching → dedupe → grouping → cooldown → actions."""
import logging
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.monitors.constants import LARGE_TRANSFER, Severity

from .models import Alert, AlertRule

logger = logging.getLogger("chainsentinel.alerts")


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
def rule_matches_event(rule: AlertRule, event) -> bool:
    if rule.trigger_on != event.status:
        return False
    if rule.wallet_monitor_id and event.wallet_monitor_id != rule.wallet_monitor_id:
        return False
    if rule.contract_monitor_id and event.contract_monitor_id != rule.contract_monitor_id:
        return False
    if rule.chain_id and event.chain_id != rule.chain_id:
        return False

    if rule.event_types:
        type_match = event.event_type in rule.event_types
        large_match = LARGE_TRANSFER in rule.event_types and event.is_large
        if not (type_match or large_match):
            return False

    if rule.token_address and (event.token_address or "").lower() != rule.token_address.lower():
        return False
    if rule.from_address and (event.from_address or "").lower() != rule.from_address.lower():
        return False
    if rule.to_address and (event.to_address or "").lower() != rule.to_address.lower():
        return False
    if rule.spender_address and (event.spender_address or "").lower() != rule.spender_address.lower():
        return False
    if rule.topic0 and (event.topic0 or "").lower() != rule.topic0.lower():
        return False

    if rule.min_amount_wei is not None:
        if event.amount_wei is None or Decimal(event.amount_wei) < rule.min_amount_wei:
            return False
    if rule.max_amount_wei is not None:
        if event.amount_wei is None or Decimal(event.amount_wei) > rule.max_amount_wei:
            return False
    return True


def group_fingerprint(rule: AlertRule, event) -> str:
    """Stable key describing 'the same kind of alert' for grouping/cooldown."""
    parts = [
        str(rule.pk),
        event.event_type,
        (event.token_address or "").lower(),
        (event.from_address or "").lower(),
        (event.to_address or "").lower(),
        (event.spender_address or "").lower(),
    ]
    return ":".join(parts)[:200]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def format_amount(event) -> str:
    if event.amount_wei is None:
        return ""
    amount = Decimal(event.amount_wei)
    if event.event_type.startswith("native"):
        symbol = event.chain.native_symbol
        decimals = 18
    else:
        symbol = event.token_symbol or "tokens"
        decimals = event.token_decimals if event.token_decimals is not None else None
    if decimals is None:
        return f"{amount} raw units of {symbol}"
    scaled = amount / (Decimal(10) ** decimals)
    return f"{scaled.normalize():f} {symbol}"


def build_alert_content(rule: AlertRule, event) -> tuple[str, str]:
    amount_text = format_amount(event)
    label = event.get_event_type_display()
    monitor = event.monitor
    title = f"{rule.name}: {label}"
    if amount_text:
        title += f" of {amount_text}"
    lines = [
        f"Rule: {rule.name}",
        f"Event: {label}" + (f" ({amount_text})" if amount_text else ""),
        f"Monitor: {monitor.name if monitor else 'n/a'}",
        f"Chain: {event.chain.name}",
        f"Tx: {event.tx_hash}",
        f"Block: #{event.block_number}",
    ]
    if event.from_address:
        lines.append(f"From: {event.from_address}")
    if event.to_address:
        lines.append(f"To: {event.to_address}")
    if event.spender_address:
        lines.append(f"Spender: {event.spender_address}")
    if event.is_large:
        lines.append("⚠ Large-transfer threshold exceeded.")
    return title[:255], "\n".join(lines)


# ---------------------------------------------------------------------------
# Evaluation entry point
# ---------------------------------------------------------------------------
def evaluate_event(event) -> list[Alert]:
    """Run every active rule in the event's workspace against the event."""
    rules = AlertRule.objects.filter(
        workspace_id=event.workspace_id, is_active=True
    ).select_related("webhook", "chain")

    created: list[Alert] = []
    for rule in rules:
        try:
            alert = _evaluate_rule(rule, event)
        except Exception as exc:  # noqa: BLE001 — one bad rule must not kill the batch
            from apps.audit.services import log_system_error

            log_system_error(
                source="alerts",
                message=f"Rule evaluation failed (rule={rule.pk}, event={event.pk})",
                exc=exc,
            )
            continue
        if alert is not None:
            created.append(alert)
    return created


def _evaluate_rule(rule: AlertRule, event) -> Alert | None:
    if not rule_matches_event(rule, event):
        return None

    now = timezone.now()
    dedupe_key = f"rule:{rule.pk}:event:{event.pk}"
    fingerprint = group_fingerprint(rule, event)

    # 1) Exact dedupe — this rule already alerted for this event.
    if Alert.objects.filter(dedupe_key=dedupe_key).exists():
        return None

    # 2) Grouping / debounce — fold into a recent open alert of the same kind.
    if rule.group_window_seconds:
        window_start = now - timedelta(seconds=rule.group_window_seconds)
        grouped = (
            Alert.objects.filter(
                rule=rule,
                group_key=fingerprint,
                status=Alert.Status.OPEN,
                last_seen_at__gte=window_start,
            )
            .order_by("-last_seen_at")
            .first()
        )
        if grouped:
            grouped.count += 1
            grouped.last_seen_at = now
            grouped.save(update_fields=["count", "last_seen_at"])
            return None  # no new alert, no repeat actions

    # 3) Cooldown — suppress fresh alerts for this fingerprint for N seconds.
    if rule.cooldown_seconds:
        cooldown_key = f"alert:cooldown:{fingerprint}"
        if not cache.add(cooldown_key, "1", timeout=rule.cooldown_seconds):
            return None

    severity = rule.severity or event.severity or Severity.MEDIUM
    title, message = build_alert_content(rule, event)

    try:
        with transaction.atomic():
            alert = Alert.objects.create(
                workspace_id=event.workspace_id,
                rule=rule,
                event=event,
                title=title,
                message=message,
                severity=severity,
                dedupe_key=dedupe_key,
                group_key=fingerprint,
                first_seen_at=now,
                last_seen_at=now,
            )
    except IntegrityError:
        return None  # concurrent duplicate — dedupe constraint won

    AlertRule.objects.filter(pk=rule.pk).update(last_triggered_at=now)
    _fire_actions(rule, alert, event)
    return alert


def _fire_actions(rule: AlertRule, alert: Alert, event) -> None:
    from apps.notifications.services import notify_workspace
    from apps.webhooks.services import dispatch_alert_webhook

    if rule.notify_in_app or rule.notify_email:
        notify_workspace(
            workspace=alert.workspace,
            type="alert",
            severity=alert.severity,
            title=alert.title,
            body=alert.message,
            link=f"/app/alerts/{alert.pk}",
            alert=alert,
            in_app=rule.notify_in_app,
            send_email=rule.notify_email,
            email_template="critical_alert",
            email_context={"alert": alert, "event": event},
        )

    if rule.notify_webhook:
        dispatch_alert_webhook(rule=rule, alert=alert, event=event)

    # Telegram / Slack are v1 placeholders: modelled, surfaced in the UI as
    # "coming soon", intentionally not delivering anywhere yet.
    if rule.telegram_enabled or rule.slack_enabled:
        logger.info(
            "Rule %s has placeholder integrations enabled (telegram=%s slack=%s) — skipped.",
            rule.pk, rule.telegram_enabled, rule.slack_enabled,
        )
