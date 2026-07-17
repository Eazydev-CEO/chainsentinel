"""Monitor domain services."""
from django.db import transaction

from . import abi as abi_tools
from .models import ContractMonitor, EventSubscription


@transaction.atomic
def sync_subscriptions(monitor: ContractMonitor) -> list[EventSubscription]:
    """(Re)build EventSubscription rows from the monitor's ABI + selections."""
    if monitor.abi_document is None:
        monitor.subscriptions.all().delete()
        return []

    available = {e["name"]: e for e in abi_tools.extract_events(monitor.abi_document.abi)}
    selected = [name for name in (monitor.selected_events or []) if name in available]

    keep_signatures = set()
    subscriptions: list[EventSubscription] = []
    abi_entries = {
        entry.get("name"): entry
        for entry in monitor.abi_document.abi
        if entry.get("type") == "event"
    }

    for name in selected:
        meta = available[name]
        fragment = abi_entries.get(name)
        filters = (monitor.topic_filters or {}).get(name, {})
        sub, _ = EventSubscription.objects.update_or_create(
            contract_monitor=monitor,
            signature=meta["signature"],
            defaults={
                "event_name": name,
                "topic0": meta["topic0"],
                "abi_fragment": fragment,
                "indexed_filters": filters,
                "is_active": True,
            },
        )
        keep_signatures.add(meta["signature"])
        subscriptions.append(sub)

    monitor.subscriptions.exclude(signature__in=keep_signatures).delete()
    return subscriptions
