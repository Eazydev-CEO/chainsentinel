from django.db import models
from django.utils import timezone


class Chain(models.Model):
    """A supported EVM network."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    chain_id = models.BigIntegerField(unique=True)
    native_symbol = models.CharField(max_length=20, default="ETH")
    explorer_url = models.URLField(blank=True)  # e.g. https://sepolia.etherscan.io
    is_testnet = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False)
    required_confirmations = models.PositiveIntegerField(default=12)
    block_time_seconds = models.FloatField(default=12.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cs_chain"
        ordering = ["name"]

    def __str__(self) -> str:
        suffix = " (testnet)" if self.is_testnet else ""
        return f"{self.name}{suffix}"

    def explorer_tx_url(self, tx_hash: str) -> str:
        return f"{self.explorer_url.rstrip('/')}/tx/{tx_hash}" if self.explorer_url else ""

    def explorer_address_url(self, address: str) -> str:
        return f"{self.explorer_url.rstrip('/')}/address/{address}" if self.explorer_url else ""


class RpcProvider(models.Model):
    """An RPC endpoint for a chain. Failover walks providers by priority."""

    class HealthStatus(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        DEGRADED = "degraded", "Degraded"
        UNHEALTHY = "unhealthy", "Unhealthy"
        UNKNOWN = "unknown", "Unknown"

    chain = models.ForeignKey(Chain, on_delete=models.CASCADE, related_name="providers")
    name = models.CharField(max_length=100)
    http_endpoint = models.URLField(max_length=500)
    ws_endpoint = models.CharField(max_length=500, blank=True)
    priority = models.PositiveIntegerField(default=100)  # lower = tried first
    is_active = models.BooleanField(default=True)
    rate_limit_per_second = models.PositiveIntegerField(default=10)

    health_status = models.CharField(
        max_length=12, choices=HealthStatus.choices, default=HealthStatus.UNKNOWN
    )
    consecutive_failures = models.PositiveIntegerField(default=0)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    last_failure_reason = models.CharField(max_length=500, blank=True)
    last_latency_ms = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cs_rpc_provider"
        ordering = ["chain", "priority"]
        indexes = [models.Index(fields=["chain", "is_active", "priority"])]

    def __str__(self) -> str:
        return f"{self.chain.slug}/{self.name}"

    def record_success(self, latency_ms: int | None = None) -> None:
        now = timezone.now()
        # Skip the DB write when nothing meaningful changes (hot path).
        if (
            self.health_status == self.HealthStatus.HEALTHY
            and self.consecutive_failures == 0
            and self.last_success_at is not None
            and (now - self.last_success_at).total_seconds() < 60
        ):
            return
        self.consecutive_failures = 0
        self.health_status = self.HealthStatus.HEALTHY
        self.last_success_at = now
        if latency_ms is not None:
            self.last_latency_ms = latency_ms
        self.save(
            update_fields=[
                "consecutive_failures",
                "health_status",
                "last_success_at",
                "last_latency_ms",
                "updated_at",
            ]
        )

    def record_failure(self, reason: str, unhealthy_threshold: int = 5) -> None:
        self.consecutive_failures += 1
        self.last_failure_at = timezone.now()
        self.last_failure_reason = reason[:500]
        if self.consecutive_failures >= unhealthy_threshold:
            self.health_status = self.HealthStatus.UNHEALTHY
        else:
            self.health_status = self.HealthStatus.DEGRADED
        self.save(
            update_fields=[
                "consecutive_failures",
                "health_status",
                "last_failure_at",
                "last_failure_reason",
                "updated_at",
            ]
        )


class RpcProviderHealthLog(models.Model):
    provider = models.ForeignKey(RpcProvider, on_delete=models.CASCADE, related_name="health_logs")
    checked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ok = models.BooleanField()
    latency_ms = models.IntegerField(null=True, blank=True)
    block_number = models.BigIntegerField(null=True, blank=True)
    error = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "cs_rpc_provider_health_log"
        ordering = ["-checked_at"]

    def __str__(self) -> str:
        return f"{self.provider} ok={self.ok} @ {self.checked_at:%H:%M:%S}"
