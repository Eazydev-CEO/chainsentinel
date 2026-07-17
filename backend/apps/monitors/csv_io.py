"""Wallet-monitor CSV import/export.

Import rules:
  * validate everything before touching the DB,
  * report row-level errors,
  * import valid rows atomically — an invalid row is never partially created,
  * detect duplicates both inside the file and against existing monitors.
"""
import csv
import io

from django.conf import settings
from django.db import transaction

from .models import MonitorCsvImport, WalletMonitor
from .serializers import WalletMonitorSerializer

EXPORT_COLUMNS = [
    "name",
    "address",
    "chain",
    "direction",
    "event_types",
    "token_contract",
    "min_value_wei",
    "large_tx_threshold_wei",
    "severity",
    "tags",
    "notes",
]

REQUIRED_COLUMNS = {"name", "address", "chain"}
LIST_SEPARATOR = "|"

DEFAULT_EVENT_TYPES = ["native_transfer", "erc20_transfer"]


class CsvImportError(Exception):
    """File-level problem (encoding, size, headers)."""


def _decode_upload(uploaded_file) -> str:
    if uploaded_file.size > settings.CSV_IMPORT_MAX_BYTES:
        raise CsvImportError(
            f"File is too large (max {settings.CSV_IMPORT_MAX_BYTES // 1024} KB)."
        )
    raw = uploaded_file.read()
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvImportError("File must be UTF-8 encoded CSV.")


def _row_to_payload(row: dict) -> dict:
    def clean(key: str) -> str:
        return (row.get(key) or "").strip()

    payload: dict = {
        "name": clean("name"),
        "address": clean("address"),
        "chain": clean("chain").lower(),
        "direction": clean("direction").lower() or "both",
        "severity": clean("severity").lower() or "medium",
        "token_contract": clean("token_contract"),
        "notes": clean("notes")[:2000],
    }
    event_types = [
        e.strip().lower() for e in clean("event_types").split(LIST_SEPARATOR) if e.strip()
    ]
    payload["event_types"] = event_types or DEFAULT_EVENT_TYPES
    payload["tags"] = [t.strip() for t in clean("tags").split(LIST_SEPARATOR) if t.strip()]
    for money_field in ("min_value_wei", "large_tx_threshold_wei"):
        value = clean(money_field)
        if value:
            payload[money_field] = value
    return payload


def import_wallet_monitors(*, workspace, uploaded_file, created_by) -> MonitorCsvImport:
    """Validate + import a CSV. Returns the stored import report."""
    text = _decode_upload(uploaded_file)
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CsvImportError("CSV appears to be empty.")

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise CsvImportError(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Expected header: {','.join(EXPORT_COLUMNS)}"
        )

    rows = list(reader)
    if len(rows) > settings.CSV_IMPORT_MAX_ROWS:
        raise CsvImportError(f"Too many rows (max {settings.CSV_IMPORT_MAX_ROWS}).")

    results = []
    seen_in_file: set[tuple[str, str]] = set()
    valid_entries: list[tuple[int, WalletMonitorSerializer]] = []

    for index, raw_row in enumerate(rows, start=2):  # header is row 1
        normalized = {(k or "").strip().lower(): v for k, v in raw_row.items()}
        payload = _row_to_payload(normalized)
        serializer = WalletMonitorSerializer(
            data=payload, context={"workspace": workspace}
        )
        if not serializer.is_valid():
            results.append(
                {
                    "row": index,
                    "status": "error",
                    "name": payload.get("name") or "(unnamed)",
                    "address": payload.get("address", ""),
                    "errors": _flatten_errors(serializer.errors),
                }
            )
            continue

        chain = serializer.validated_data["chain"]
        address = serializer.validated_data["address"]
        file_key = (chain.slug, address.lower())
        if file_key in seen_in_file:
            results.append(
                {
                    "row": index,
                    "status": "error",
                    "name": payload["name"],
                    "address": address,
                    "errors": ["Duplicate of an earlier row in this file."],
                }
            )
            continue
        seen_in_file.add(file_key)
        valid_entries.append((index, serializer))

    created_ids: list[int] = []
    with transaction.atomic():
        for index, serializer in valid_entries:
            monitor = serializer.save(workspace=workspace, created_by=created_by)
            created_ids.append(monitor.pk)
            results.append(
                {
                    "row": index,
                    "status": "created",
                    "name": monitor.name,
                    "address": monitor.address,
                    "monitor_id": monitor.pk,
                }
            )

    results.sort(key=lambda r: r["row"])
    created_count = sum(1 for r in results if r["status"] == "created")
    failed_count = sum(1 for r in results if r["status"] == "error")

    return MonitorCsvImport.objects.create(
        workspace=workspace,
        created_by=created_by,
        filename=getattr(uploaded_file, "name", "import.csv")[:255],
        total_rows=len(rows),
        created_count=created_count,
        failed_count=failed_count,
        report={"rows": results, "created_ids": created_ids},
    )


def _flatten_errors(errors) -> list[str]:
    flat: list[str] = []
    if isinstance(errors, dict):
        for field, messages in errors.items():
            if isinstance(messages, (list, tuple)):
                flat.extend(f"{field}: {m}" for m in messages)
            else:
                flat.append(f"{field}: {messages}")
    elif isinstance(errors, (list, tuple)):
        flat.extend(str(m) for m in errors)
    else:
        flat.append(str(errors))
    return flat


def export_wallet_monitors(workspace) -> str:
    """Render the workspace's wallet monitors as CSV text."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXPORT_COLUMNS)
    monitors = (
        WalletMonitor.objects.filter(workspace=workspace)
        .select_related("chain")
        .order_by("chain__slug", "name")
    )
    for m in monitors:
        writer.writerow(
            [
                m.name,
                m.address,
                m.chain.slug,
                m.direction,
                LIST_SEPARATOR.join(m.event_types or []),
                m.token_contract,
                str(m.min_value_wei or ""),
                str(m.large_tx_threshold_wei or ""),
                m.severity,
                LIST_SEPARATOR.join(m.tags or []),
                (m.notes or "").replace("\r", " ").replace("\n", " ")[:500],
            ]
        )
    return buffer.getvalue()
