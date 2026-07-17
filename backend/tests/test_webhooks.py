"""Webhooks: HMAC signatures, SSRF guard, delivery, retries, replay."""
import json
from datetime import timedelta

import pytest
import requests
from django.utils import timezone

from apps.webhooks import tasks as webhook_tasks
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint
from apps.webhooks.signer import sign_payload, signature_header, verify_signature
from apps.webhooks.ssrf import WebhookSecurityError, validate_webhook_url

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# HMAC signing
# ---------------------------------------------------------------------------
class TestSigner:
    def test_signature_is_deterministic_hmac_sha256(self):
        sig = sign_payload("whsec_abc", 1700000000, '{"a":1}')
        assert sig == sign_payload("whsec_abc", 1700000000, '{"a":1}')
        assert len(sig) == 64  # hex sha256

    def test_signature_changes_with_secret_timestamp_and_body(self):
        base = sign_payload("s1", 1, "b")
        assert base != sign_payload("s2", 1, "b")
        assert base != sign_payload("s1", 2, "b")
        assert base != sign_payload("s1", 1, "B")

    def test_header_format_and_verify(self):
        header = signature_header("whsec_k", 1700000000, "payload")
        assert header.startswith("t=1700000000,v1=")
        v1 = header.split("v1=")[1]
        assert verify_signature("whsec_k", 1700000000, "payload", v1) is True
        assert verify_signature("whsec_k", 1700000000, "tampered", v1) is False


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------
class TestSsrfGuard:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/hook",
            "http://localhost/hook",
            "http://sub.localhost/hook",
            "http://10.0.0.8/hook",
            "http://172.16.5.5/hook",
            "http://192.168.1.10/hook",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/hook",
            "http://[fc00::1]/hook",
            "http://[::ffff:10.0.0.1]/hook",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://0.0.0.0/hook",
        ],
    )
    def test_private_and_metadata_destinations_blocked(self, url):
        with pytest.raises(WebhookSecurityError):
            validate_webhook_url(url)

    @pytest.mark.parametrize("url", ["ftp://example.com/x", "file:///etc/passwd", "gopher://x"])
    def test_non_http_schemes_blocked(self, url):
        with pytest.raises(WebhookSecurityError, match="http"):
            validate_webhook_url(url)

    def test_unusual_ports_blocked(self):
        with pytest.raises(WebhookSecurityError, match="Port 22"):
            validate_webhook_url("https://8.8.8.8:22/hook")

    def test_credentials_in_url_blocked(self):
        with pytest.raises(WebhookSecurityError, match="credentials"):
            validate_webhook_url("https://user:pass@8.8.8.8/hook")

    def test_public_ip_allowed(self):
        assert validate_webhook_url("https://8.8.8.8/hook") == ["8.8.8.8"]

    def test_hostname_resolving_to_private_ip_blocked(self, monkeypatch):
        import socket

        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 443))],
        )
        with pytest.raises(WebhookSecurityError, match="private"):
            validate_webhook_url("https://rebind.example.com/hook")

    def test_hostname_resolving_to_public_ip_allowed(self, monkeypatch):
        import socket

        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        )
        assert validate_webhook_url("https://ok.example.com/hook") == ["93.184.216.34"]

    def test_structural_check_skips_dns(self):
        # resolve=False is what serializers use — no network in validation.
        assert validate_webhook_url("https://any-host.example/hook", resolve=False) == []


# ---------------------------------------------------------------------------
# Delivery task
# ---------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


@pytest.fixture
def endpoint(workspace):
    ep = WebhookEndpoint(
        workspace=workspace,
        name="Receiver",
        url="https://8.8.8.8/hook",  # public IP literal — no DNS in tests
        enabled=True,
        event_types=["alert.triggered", "test.ping"],
        max_retries=3,
    )
    ep.set_secret("whsec_test_secret")
    ep.save()
    return ep


@pytest.fixture
def delivery(endpoint):
    return WebhookDelivery.objects.create(
        endpoint=endpoint,
        workspace=endpoint.workspace,
        event_type="alert.triggered",
        payload={"alert_id": 1, "title": "Test"},
        idempotency_key="ep:test:alert:1",
        max_attempts=3,
    )


class TestDeliveryTask:
    def test_successful_delivery_signs_and_records(self, delivery, endpoint, monkeypatch):
        captured = {}

        def fake_post(url, data=None, headers=None, timeout=None, allow_redirects=None):
            captured.update(url=url, data=data, headers=headers, redirects=allow_redirects)
            return FakeResponse(200)

        monkeypatch.setattr(webhook_tasks.requests, "post", fake_post)
        webhook_tasks.deliver_webhook(delivery.pk)

        delivery.refresh_from_db()
        endpoint.refresh_from_db()
        assert delivery.status == WebhookDelivery.Status.SUCCESS
        assert delivery.response_status == 200
        assert delivery.delivered_at is not None
        assert endpoint.last_status == "success"

        # Redirects must not be followed.
        assert captured["redirects"] is False

        # Signature verifies against the raw body.
        headers = captured["headers"]
        body = captured["data"].decode()
        ts = headers["X-ChainSentinel-Timestamp"]
        v1 = headers["X-ChainSentinel-Signature"].split("v1=")[1]
        assert verify_signature("whsec_test_secret", ts, body, v1)
        assert headers["X-ChainSentinel-Event"] == "alert.triggered"
        assert json.loads(body)["data"]["alert_id"] == 1

    def test_failure_schedules_exponential_retry(self, delivery, endpoint, monkeypatch, settings):
        settings.WEBHOOK_BACKOFF_BASE_SECONDS = 60
        monkeypatch.setattr(
            webhook_tasks.requests, "post", lambda *a, **k: FakeResponse(500)
        )

        before = timezone.now()
        webhook_tasks.deliver_webhook(delivery.pk)
        delivery.refresh_from_db()
        assert delivery.status == WebhookDelivery.Status.RETRYING
        assert delivery.attempt_count == 1
        assert delivery.failure_reason == "http_500"
        first_delay = (delivery.next_retry_at - before).total_seconds()
        assert 55 <= first_delay <= 65  # ~60s

        before = timezone.now()
        webhook_tasks.deliver_webhook(delivery.pk)
        delivery.refresh_from_db()
        second_delay = (delivery.next_retry_at - before).total_seconds()
        assert 115 <= second_delay <= 125  # ~120s — doubled

    def test_exhausted_after_max_attempts_notifies(self, delivery, endpoint, user, monkeypatch):
        from apps.notifications.models import Notification

        monkeypatch.setattr(
            webhook_tasks.requests, "post", lambda *a, **k: FakeResponse(503)
        )
        for _ in range(3):
            webhook_tasks.deliver_webhook(delivery.pk)

        delivery.refresh_from_db()
        assert delivery.status == WebhookDelivery.Status.EXHAUSTED
        assert delivery.attempt_count == 3
        assert Notification.objects.filter(user=user, type="webhook_failed").exists()

    def test_redirect_is_a_failure_not_followed(self, delivery, monkeypatch):
        monkeypatch.setattr(
            webhook_tasks.requests, "post", lambda *a, **k: FakeResponse(302)
        )
        webhook_tasks.deliver_webhook(delivery.pk)
        delivery.refresh_from_db()
        assert delivery.failure_reason == "redirect_302_not_followed"

    def test_connection_error_classified(self, delivery, monkeypatch):
        def boom(*a, **k):
            raise requests.exceptions.ConnectionError("refused")

        monkeypatch.setattr(webhook_tasks.requests, "post", boom)
        webhook_tasks.deliver_webhook(delivery.pk)
        delivery.refresh_from_db()
        assert delivery.failure_reason == "connection_error"

    def test_ssrf_recheck_blocks_at_send_time(self, endpoint, monkeypatch):
        # URL passed structural validation at save; simulate later DNS pointing inside.
        endpoint.url = "http://169.254.169.254/latest"
        endpoint.save()
        bad = WebhookDelivery.objects.create(
            endpoint=endpoint,
            workspace=endpoint.workspace,
            event_type="test.ping",
            payload={},
            idempotency_key="ep:test:ssrf",
            max_attempts=1,
        )
        called = []
        monkeypatch.setattr(webhook_tasks.requests, "post", lambda *a, **k: called.append(1))
        webhook_tasks.deliver_webhook(bad.pk)
        bad.refresh_from_db()
        assert called == []  # request never left the building
        assert bad.failure_reason.startswith("blocked:")

    def test_disabled_endpoint_never_delivers(self, delivery, endpoint, monkeypatch):
        endpoint.enabled = False
        endpoint.save()
        called = []
        monkeypatch.setattr(webhook_tasks.requests, "post", lambda *a, **k: called.append(1))
        webhook_tasks.deliver_webhook(delivery.pk)
        delivery.refresh_from_db()
        assert called == []
        assert delivery.status == WebhookDelivery.Status.EXHAUSTED

    def test_success_is_terminal_for_repeat_invocations(self, delivery, monkeypatch):
        monkeypatch.setattr(webhook_tasks.requests, "post", lambda *a, **k: FakeResponse(200))
        webhook_tasks.deliver_webhook(delivery.pk)
        result = webhook_tasks.deliver_webhook(delivery.pk)  # e.g. duplicate queue entry
        assert result == {"skipped": "already success"}
        delivery.refresh_from_db()
        assert delivery.attempt_count == 1


class TestRetryScanner:
    def test_due_retries_are_requeued(self, delivery, monkeypatch):
        delivery.status = WebhookDelivery.Status.RETRYING
        delivery.next_retry_at = timezone.now() - timedelta(seconds=5)
        delivery.save()

        requeued = []
        monkeypatch.setattr(webhook_tasks.deliver_webhook, "delay", lambda pk: requeued.append(pk))
        result = webhook_tasks.retry_due_deliveries()
        assert delivery.pk in requeued
        assert result["requeued"] >= 1

    def test_future_retries_left_alone(self, delivery, monkeypatch):
        delivery.status = WebhookDelivery.Status.RETRYING
        delivery.next_retry_at = timezone.now() + timedelta(hours=1)
        delivery.save()
        requeued = []
        monkeypatch.setattr(webhook_tasks.deliver_webhook, "delay", lambda pk: requeued.append(pk))
        webhook_tasks.retry_due_deliveries()
        assert delivery.pk not in requeued

    def test_stale_pending_rescued_after_crash(self, endpoint, monkeypatch):
        stale = WebhookDelivery.objects.create(
            endpoint=endpoint,
            workspace=endpoint.workspace,
            event_type="alert.triggered",
            payload={},
            idempotency_key="ep:test:stale",
        )
        WebhookDelivery.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - timedelta(minutes=30)
        )
        requeued = []
        monkeypatch.setattr(webhook_tasks.deliver_webhook, "delay", lambda pk: requeued.append(pk))
        webhook_tasks.retry_due_deliveries()
        assert stale.pk in requeued


class TestReplayAndApi:
    def test_replay_creates_linked_delivery(self, api, workspace, endpoint, delivery, monkeypatch):
        monkeypatch.setattr(webhook_tasks.deliver_webhook, "delay", lambda pk: None)
        delivery.status = WebhookDelivery.Status.EXHAUSTED
        delivery.save()

        response = api.post(
            f"/api/v1/webhook-deliveries/{delivery.pk}/replay/?workspace={workspace.pk}"
        )
        assert response.status_code == 202, response.content
        replay = WebhookDelivery.objects.get(replay_of=delivery)
        assert replay.payload == delivery.payload
        assert replay.status == WebhookDelivery.Status.PENDING

    def test_secret_never_exposed_after_creation(self, api, workspace, endpoint):
        response = api.get(f"/api/v1/webhooks/{endpoint.pk}/?workspace={workspace.pk}")
        assert response.status_code == 200
        assert "secret" not in response.json()
        assert "secret_encrypted" not in response.json()

    def test_create_returns_secret_once(self, api, workspace, monkeypatch):
        response = api.post(
            f"/api/v1/webhooks/?workspace={workspace.pk}",
            {
                "name": "New hook",
                "url": "https://8.8.8.8/hook",
                "event_types": ["alert.triggered"],
            },
            format="json",
        )
        assert response.status_code == 201, response.content
        body = response.json()
        assert body["secret"].startswith("whsec_")

        # Stored encrypted, decrypts to the same value.
        stored = WebhookEndpoint.objects.get(pk=body["id"])
        assert stored.secret_encrypted != body["secret"]
        assert stored.get_secret() == body["secret"]

    def test_regenerate_secret_rotates(self, api, workspace, endpoint):
        old = endpoint.get_secret()
        response = api.post(
            f"/api/v1/webhooks/{endpoint.pk}/regenerate-secret/?workspace={workspace.pk}"
        )
        assert response.status_code == 200
        new_secret = response.json()["secret"]
        assert new_secret != old
        endpoint.refresh_from_db()
        assert endpoint.get_secret() == new_secret

    def test_private_url_rejected_at_api_layer(self, api, workspace):
        response = api.post(
            f"/api/v1/webhooks/?workspace={workspace.pk}",
            {"name": "Bad", "url": "http://127.0.0.1/hook", "event_types": ["test.ping"]},
            format="json",
        )
        assert response.status_code == 400
