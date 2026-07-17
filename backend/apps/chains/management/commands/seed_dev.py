"""Development seed data. Refuses to run outside DEBUG.

Everything created here is clearly labelled as demo/test data. RPC endpoints
come exclusively from environment variables; when a variable is empty the
provider row is created INACTIVE with a placeholder URL so nothing ever
calls a fake endpoint.
"""
import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

DEMO_TAG = "demo-seed"

CHAINS = [
    # (name, slug, chain_id, symbol, explorer, testnet, confirmations, block_time, env_prefix)
    ("Ethereum", "ethereum", 1, "ETH", "https://etherscan.io", False, 12, 12.0, "RPC_ETHEREUM"),
    ("Ethereum Sepolia", "ethereum-sepolia", 11155111, "ETH", "https://sepolia.etherscan.io", True, 6, 12.0, "RPC_ETHEREUM_SEPOLIA"),
    ("BNB Smart Chain", "bsc", 56, "BNB", "https://bscscan.com", False, 15, 3.0, "RPC_BSC"),
    ("BSC Testnet", "bsc-testnet", 97, "tBNB", "https://testnet.bscscan.com", True, 10, 3.0, "RPC_BSC_TESTNET"),
    ("Polygon", "polygon", 137, "POL", "https://polygonscan.com", False, 30, 2.1, "RPC_POLYGON"),
    ("Polygon Amoy", "polygon-amoy", 80002, "POL", "https://amoy.polygonscan.com", True, 15, 2.1, "RPC_POLYGON_AMOY"),
    ("Base", "base", 8453, "ETH", "https://basescan.org", False, 12, 2.0, "RPC_BASE"),
    ("Base Sepolia", "base-sepolia", 84532, "ETH", "https://sepolia.basescan.org", True, 6, 2.0, "RPC_BASE_SEPOLIA"),
    ("Arbitrum One", "arbitrum", 42161, "ETH", "https://arbiscan.io", False, 20, 0.3, "RPC_ARBITRUM"),
    ("Arbitrum Sepolia", "arbitrum-sepolia", 421614, "ETH", "https://sepolia.arbiscan.io", True, 10, 0.3, "RPC_ARBITRUM_SEPOLIA"),
    ("Optimism", "optimism", 10, "ETH", "https://optimistic.etherscan.io", False, 12, 2.0, "RPC_OPTIMISM"),
    ("Optimism Sepolia", "optimism-sepolia", 11155420, "ETH", "https://sepolia-optimism.etherscan.io", True, 6, 2.0, "RPC_OPTIMISM_SEPOLIA"),
]

# Well-known public addresses used purely as demo monitor targets (read-only).
DEMO_WALLET = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # vitalik.eth
DEMO_TOKEN_SEPOLIA = "0x7169D38820dfd117C3FA1f22a697dBA58d90BA06"  # test USDT (Sepolia)

ERC20_ABI_MIN = [
    {
        "type": "event",
        "name": "Transfer",
        "anonymous": False,
        "inputs": [
            {"name": "from", "type": "address", "indexed": True},
            {"name": "to", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
    {
        "type": "event",
        "name": "Approval",
        "anonymous": False,
        "inputs": [
            {"name": "owner", "type": "address", "indexed": True},
            {"name": "spender", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed development data (chains, providers, demo workspace/monitors). DEBUG only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_dev only runs with DJANGO_DEBUG=true (development).")

        from apps.accounts.models import User, UserProfile
        from apps.alerts.models import Alert, AlertRule
        from apps.chains.models import Chain, RpcProvider
        from apps.events.models import BlockchainEvent, EventStatus
        from apps.monitors import abi as abi_tools
        from apps.monitors.constants import Severity
        from apps.monitors.models import ContractAbi, ContractMonitor, WalletMonitor
        from apps.monitors.services import sync_subscriptions
        from apps.webhooks.models import WebhookDelivery, WebhookEndpoint
        from apps.workspaces.services import create_workspace

        # ------------------------------------------------------------------ chains
        chains = {}
        for name, slug, chain_id, symbol, explorer, testnet, confs, block_time, env in CHAINS:
            chain, created = Chain.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "chain_id": chain_id,
                    "native_symbol": symbol,
                    "explorer_url": explorer,
                    "is_testnet": testnet,
                    "required_confirmations": confs,
                    "block_time_seconds": block_time,
                    # Mainnets seeded INACTIVE by policy; testnets active.
                    "is_active": testnet,
                },
            )
            chains[slug] = chain

            http_url = os.environ.get(f"{env}_HTTP", "").strip()
            ws_url = os.environ.get(f"{env}_WS", "").strip()
            RpcProvider.objects.update_or_create(
                chain=chain,
                name="primary-env",
                defaults={
                    "http_endpoint": http_url or f"https://rpc-placeholder.invalid/{slug}",
                    "ws_endpoint": ws_url,
                    "priority": 10,
                    # Providers without a real endpoint stay inactive.
                    "is_active": bool(http_url),
                    "rate_limit_per_second": 10,
                },
            )
            state = "active" if http_url else "placeholder (inactive)"
            self.stdout.write(f"  chain {slug}: provider {state}")

        # ------------------------------------------------------------- demo tenant
        demo_password = settings.SEED_DEMO_PASSWORD
        owner, created = User.objects.get_or_create(
            email="demo@chainsentinel.local",
            defaults={"first_name": "Demo", "last_name": "Owner", "is_email_verified": True},
        )
        if created:
            owner.set_password(demo_password)
            owner.email_verified_at = timezone.now()
            owner.save()
            UserProfile.objects.get_or_create(user=owner)

        analyst, created = User.objects.get_or_create(
            email="analyst@chainsentinel.local",
            defaults={"first_name": "Demo", "last_name": "Analyst", "is_email_verified": True},
        )
        if created:
            analyst.set_password(demo_password)
            analyst.save()
            UserProfile.objects.get_or_create(user=analyst)

        from apps.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole

        workspace = Workspace.objects.filter(slug="demo-workspace-test-data").first()
        if workspace is None:
            workspace = create_workspace(name="Demo Workspace [TEST DATA]", owner=owner)
            workspace.slug = "demo-workspace-test-data"
            workspace.save(update_fields=["slug"])
        WorkspaceMember.objects.get_or_create(
            workspace=workspace, user=analyst, defaults={"role": WorkspaceRole.ANALYST}
        )

        sepolia = chains["ethereum-sepolia"]

        # ---------------------------------------------------------------- monitors
        wallet_monitor, _ = WalletMonitor.objects.get_or_create(
            workspace=workspace,
            chain=sepolia,
            address=DEMO_WALLET,
            defaults={
                "name": "[DEMO] Treasury wallet",
                "direction": "both",
                "event_types": ["native_transfer", "erc20_transfer", "approval"],
                "severity": Severity.MEDIUM,
                "tags": [DEMO_TAG, "treasury"],
                "notes": "Seeded demo monitor — safe to delete.",
                "created_by": owner,
                "large_tx_threshold_wei": Decimal("1000000000000000000"),  # 1 ETH
            },
        )

        parsed = abi_tools.parse_abi(ERC20_ABI_MIN)
        abi_doc, _ = ContractAbi.objects.get_or_create(
            workspace=workspace,
            sha256=abi_tools.abi_sha256(parsed),
            defaults={"name": "[DEMO] ERC-20 minimal ABI", "abi": parsed, "created_by": owner},
        )
        contract_monitor, _ = ContractMonitor.objects.get_or_create(
            workspace=workspace,
            chain=sepolia,
            address=DEMO_TOKEN_SEPOLIA,
            defaults={
                "name": "[DEMO] Test token events",
                "label": "Sepolia test USDT",
                "abi_document": abi_doc,
                "selected_events": ["Transfer", "Approval"],
                "severity": Severity.LOW,
                "tags": [DEMO_TAG],
                "notes": "Seeded demo monitor — safe to delete.",
                "created_by": owner,
            },
        )
        sync_subscriptions(contract_monitor)

        # ------------------------------------------------------------------- rules
        rule_large, _ = AlertRule.objects.get_or_create(
            workspace=workspace,
            name="[DEMO] Large transfer alert",
            defaults={
                "description": "Seeded demo rule: any large transfer on the treasury wallet.",
                "wallet_monitor": wallet_monitor,
                "event_types": ["large_transfer"],
                "severity": Severity.HIGH,
                "notify_in_app": True,
                "notify_email": False,
                "cooldown_seconds": 300,
                "created_by": owner,
            },
        )
        AlertRule.objects.get_or_create(
            workspace=workspace,
            name="[DEMO] Approval watch",
            defaults={
                "description": "Seeded demo rule: approvals granted from the treasury wallet.",
                "wallet_monitor": wallet_monitor,
                "event_types": ["approval_created", "approval_changed", "approval_for_all"],
                "severity": Severity.CRITICAL,
                "notify_in_app": True,
                "group_window_seconds": 600,
                "created_by": owner,
            },
        )

        # ------------------------------------------- sample events/alerts/deliveries
        # Clearly-labelled synthetic records so the dashboard demonstrates real
        # queries in development. They use an impossible block range (1..N) on
        # the testnet and are tagged in raw payload as seed data.
        if not BlockchainEvent.objects.filter(workspace=workspace).exists():
            now = timezone.now()
            samples = [
                (EventStatus.CONFIRMED, "native_received", Decimal("250000000000000000"), None, 3),
                (EventStatus.CONFIRMED, "erc20_received", Decimal("1500000000"), "USDT", 2),
                (EventStatus.CONFIRMED, "approval_created", Decimal("115792089237316195423570985008687907853269984665640564039457584007913129639935"), "USDT", 1),
                (EventStatus.PENDING, "native_sent", Decimal("50000000000000000"), None, 0),
            ]
            for i, (status_value, event_type, amount, symbol, hours_ago) in enumerate(samples, start=1):
                event = BlockchainEvent.objects.create(
                    workspace=workspace,
                    chain=sepolia,
                    wallet_monitor=wallet_monitor,
                    event_type=event_type,
                    status=status_value,
                    severity=Severity.MEDIUM,
                    block_number=i,
                    block_hash=f"0x{'ab' * 31}{i:02x}",
                    tx_hash=f"0x{'cd' * 31}{i:02x}",
                    log_index=None if event_type.startswith("native") else i,
                    from_address=DEMO_WALLET if "sent" in event_type else "0x000000000000000000000000000000000000dEaD",
                    to_address=DEMO_WALLET if "received" in event_type else "0x000000000000000000000000000000000000dEaD",
                    spender_address="0x1111111254EEB25477B68fb85Ed929f73A960582" if "approval" in event_type else "",
                    token_address=DEMO_TOKEN_SEPOLIA if symbol else "",
                    token_symbol=symbol or "",
                    token_decimals=6 if symbol else None,
                    amount_wei=amount,
                    confirmations_required=6,
                    occurred_at=now - timedelta(hours=hours_ago),
                    confirmed_at=now - timedelta(hours=hours_ago) if status_value == EventStatus.CONFIRMED else None,
                    idempotency_key=f"seed:{workspace.pk}:{i}",
                    raw={"seed": True, "note": "Demo/test data created by seed_dev"},
                )
                if status_value == EventStatus.CONFIRMED and "approval" not in event_type:
                    Alert.objects.get_or_create(
                        dedupe_key=f"seed:alert:{event.pk}",
                        defaults={
                            "workspace": workspace,
                            "rule": rule_large,
                            "event": event,
                            "title": f"[DEMO] {event.get_event_type_display()} on treasury wallet",
                            "message": "Seeded demo alert — safe to resolve or delete.",
                            "severity": Severity.HIGH,
                        },
                    )

        endpoint = WebhookEndpoint.objects.filter(workspace=workspace, name="[DEMO] Example receiver").first()
        if endpoint is None:
            endpoint = WebhookEndpoint(
                workspace=workspace,
                name="[DEMO] Example receiver",
                url="https://example.com/webhooks/chainsentinel",
                enabled=False,  # never actually delivers anywhere
                event_types=["alert.triggered", "event.confirmed"],
                created_by=owner,
            )
            endpoint.set_secret(WebhookEndpoint.generate_secret())
            endpoint.save()
            WebhookDelivery.objects.get_or_create(
                idempotency_key=f"seed:delivery:{workspace.pk}:1",
                defaults={
                    "endpoint": endpoint,
                    "workspace": workspace,
                    "event_type": "alert.triggered",
                    "payload": {"seed": True, "message": "Demo delivery record"},
                    "status": WebhookDelivery.Status.SUCCESS,
                    "attempt_count": 1,
                    "response_status": 200,
                    "response_time_ms": 184,
                    "delivered_at": timezone.now(),
                },
            )

        self.stdout.write(self.style.SUCCESS(
            "\nSeed complete.\n"
            f"  Demo owner:   demo@chainsentinel.local / {demo_password}\n"
            f"  Demo analyst: analyst@chainsentinel.local / {demo_password}\n"
            "  Workspace:    Demo Workspace [TEST DATA]\n"
            "  NOTE: mainnet chains are seeded INACTIVE; testnet providers activate\n"
            "  only when their RPC_*_HTTP env vars are set."
        ))
