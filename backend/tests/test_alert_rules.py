"""Alert rules: matching, dedupe, cooldown, grouping/debounce, actions."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.alerts.models import Alert, AlertRule
from apps.alerts.services import evaluate_event, rule_matches_event
from apps.events.models import BlockchainEvent, EventStatus
from apps.notifications.models import Notification

from .conftest import DEMO_WALLET, SPENDER, TOKEN_ADDRESS

pytestmark = pytest.mark.django_db


def make_event(workspace, chain, monitor, *, event_type="native_received", amount=10**18,
               status=EventStatus.CONFIRMED, is_large=False, block=100, suffix="a",
               spender="", token=""):
    return BlockchainEvent.objects.create(
        workspace=workspace,
        chain=chain,
        wallet_monitor=monitor,
        event_type=event_type,
        status=status,
        severity="medium",
        is_large=is_large,
        block_number=block,
        block_hash=f"0x{'11' * 32}",
        tx_hash=f"0x{'22' * 31}{suffix * 2}",
        log_index=None,
        from_address="0x" + "33" * 20,
        to_address=DEMO_WALLET,
        spender_address=spender,
        token_address=token,
        amount_wei=Decimal(amount),
        confirmations_required=2,
        occurred_at=timezone.now(),
        idempotency_key=f"test:{workspace.pk}:{block}:{suffix}:{event_type}",
    )


@pytest.fixture
def rule(workspace, wallet_monitor):
    return AlertRule.objects.create(
        workspace=workspace,
        name="Any native inflow",
        wallet_monitor=wallet_monitor,
        event_types=["native_received"],
        severity="high",
        notify_in_app=True,
    )


class TestMatching:
    def test_basic_match(self, workspace, chain, wallet_monitor, rule):
        event = make_event(workspace, chain, wallet_monitor)
        assert rule_matches_event(rule, event) is True

    def test_event_type_mismatch(self, workspace, chain, wallet_monitor, rule):
        event = make_event(workspace, chain, wallet_monitor, event_type="native_sent")
        assert rule_matches_event(rule, event) is False

    def test_pending_events_do_not_match_confirmed_rules(self, workspace, chain, wallet_monitor, rule):
        event = make_event(workspace, chain, wallet_monitor, status=EventStatus.PENDING)
        assert rule_matches_event(rule, event) is False

    def test_amount_bounds(self, workspace, chain, wallet_monitor, rule):
        rule.min_amount_wei = Decimal(10**18)
        rule.max_amount_wei = Decimal(5 * 10**18)
        rule.save()
        too_small = make_event(workspace, chain, wallet_monitor, amount=10**17, suffix="b")
        in_range = make_event(workspace, chain, wallet_monitor, amount=2 * 10**18, suffix="c")
        too_big = make_event(workspace, chain, wallet_monitor, amount=9 * 10**18, suffix="d")
        assert rule_matches_event(rule, too_small) is False
        assert rule_matches_event(rule, in_range) is True
        assert rule_matches_event(rule, too_big) is False

    def test_large_transfer_virtual_type(self, workspace, chain, wallet_monitor):
        rule = AlertRule.objects.create(
            workspace=workspace, name="Whale", event_types=["large_transfer"], severity="critical"
        )
        normal = make_event(workspace, chain, wallet_monitor, suffix="e")
        large = make_event(workspace, chain, wallet_monitor, is_large=True, suffix="f")
        assert rule_matches_event(rule, normal) is False
        assert rule_matches_event(rule, large) is True

    def test_spender_filter(self, workspace, chain, wallet_monitor):
        rule = AlertRule.objects.create(
            workspace=workspace,
            name="Router approvals",
            event_types=["approval_created"],
            spender_address=SPENDER,
        )
        match = make_event(
            workspace, chain, wallet_monitor,
            event_type="approval_created", spender=SPENDER, token=TOKEN_ADDRESS, suffix="g",
        )
        other = make_event(
            workspace, chain, wallet_monitor,
            event_type="approval_created", spender="0x" + "77" * 20, suffix="h",
        )
        assert rule_matches_event(rule, match) is True
        assert rule_matches_event(rule, other) is False

    def test_chain_filter(self, workspace, chain, wallet_monitor, rule, db):
        from apps.chains.models import Chain

        other_chain = Chain.objects.create(
            name="Other", slug="other", chain_id=555, is_active=True
        )
        rule.chain = other_chain
        rule.save()
        event = make_event(workspace, chain, wallet_monitor)
        assert rule_matches_event(rule, event) is False


class TestEvaluation:
    def test_alert_created_with_in_app_notifications(self, workspace, chain, wallet_monitor, rule, user):
        event = make_event(workspace, chain, wallet_monitor)
        alerts = evaluate_event(event)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.severity == "high"  # rule override
        assert alert.rule == rule
        assert alert.event == event
        assert "native received" in alert.title.lower() or "Native received" in alert.title
        assert Notification.objects.filter(user=user, alert=alert).exists()

    def test_same_event_never_alerts_twice(self, workspace, chain, wallet_monitor, rule):
        event = make_event(workspace, chain, wallet_monitor)
        assert len(evaluate_event(event)) == 1
        assert len(evaluate_event(event)) == 0  # dedupe by (rule, event)
        assert Alert.objects.count() == 1

    def test_cooldown_suppresses_new_alerts(self, workspace, chain, wallet_monitor, rule):
        rule.cooldown_seconds = 600
        rule.save()
        first = make_event(workspace, chain, wallet_monitor, suffix="j", block=101)
        second = make_event(workspace, chain, wallet_monitor, suffix="k", block=102)

        assert len(evaluate_event(first)) == 1
        assert len(evaluate_event(second)) == 0  # inside cooldown window
        assert Alert.objects.count() == 1

    def test_grouping_folds_repeats_into_one_alert(self, workspace, chain, wallet_monitor, rule):
        rule.group_window_seconds = 3600
        rule.save()
        first = make_event(workspace, chain, wallet_monitor, suffix="m", block=101)
        second = make_event(workspace, chain, wallet_monitor, suffix="n", block=102)
        third = make_event(workspace, chain, wallet_monitor, suffix="o", block=103)

        evaluate_event(first)
        evaluate_event(second)
        evaluate_event(third)

        alert = Alert.objects.get()
        assert alert.count == 3
        # Only the first occurrence notified.
        assert Notification.objects.filter(alert=alert).count() == 1

    def test_grouping_ignores_resolved_alerts(self, workspace, chain, wallet_monitor, rule, user):
        rule.group_window_seconds = 3600
        rule.save()
        first = make_event(workspace, chain, wallet_monitor, suffix="p", block=101)
        evaluate_event(first)
        alert = Alert.objects.get()
        alert.status = Alert.Status.RESOLVED
        alert.resolved_at = timezone.now()
        alert.save()

        second = make_event(workspace, chain, wallet_monitor, suffix="q", block=102)
        evaluate_event(second)
        assert Alert.objects.count() == 2  # resolved alerts don't absorb new events

    def test_inactive_rule_never_fires(self, workspace, chain, wallet_monitor, rule):
        rule.is_active = False
        rule.save()
        event = make_event(workspace, chain, wallet_monitor)
        assert evaluate_event(event) == []

    def test_severity_inherits_from_event_when_blank(self, workspace, chain, wallet_monitor, rule):
        rule.severity = ""
        rule.save()
        event = make_event(workspace, chain, wallet_monitor)
        alerts = evaluate_event(event)
        assert alerts[0].severity == "medium"  # event severity

    def test_webhook_action_creates_delivery(self, workspace, chain, wallet_monitor, monkeypatch):
        from apps.webhooks.models import WebhookDelivery, WebhookEndpoint
        from apps.webhooks import tasks as webhook_tasks

        # Don't actually attempt HTTP in eager mode.
        monkeypatch.setattr(webhook_tasks.deliver_webhook, "delay", lambda pk: None)

        endpoint = WebhookEndpoint(
            workspace=workspace,
            name="Receiver",
            url="https://receiver.example.com/hook",
            enabled=True,
            event_types=["alert.triggered"],
        )
        endpoint.set_secret(WebhookEndpoint.generate_secret())
        endpoint.save()

        AlertRule.objects.create(
            workspace=workspace,
            name="Webhook rule",
            event_types=["native_received"],
            notify_in_app=False,
            notify_webhook=True,
        )
        event = make_event(workspace, chain, wallet_monitor, suffix="r")
        evaluate_event(event)

        delivery = WebhookDelivery.objects.get()
        assert delivery.event_type == "alert.triggered"
        assert delivery.endpoint == endpoint
        assert delivery.payload["event"]["tx_hash"] == event.tx_hash
