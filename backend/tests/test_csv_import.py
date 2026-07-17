"""Wallet-monitor CSV import: validation, duplicates, row errors, atomicity."""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.monitors.csv_io import CsvImportError, export_wallet_monitors, import_wallet_monitors
from apps.monitors.models import WalletMonitor

from .conftest import DEMO_WALLET, OTHER_WALLET

pytestmark = pytest.mark.django_db

HEADER = "name,address,chain,direction,event_types,token_contract,min_value_wei,large_tx_threshold_wei,severity,tags,notes"


def upload(text: str, name: str = "monitors.csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, text.encode(), content_type="text/csv")


class TestImport:
    def test_valid_rows_imported(self, workspace, chain, user):
        csv_text = (
            f"{HEADER}\n"
            f"Treasury,{DEMO_WALLET},testnet,both,native_transfer|erc20_transfer,,,,high,ops|core,Main wallet\n"
            f"Ops,{OTHER_WALLET},testnet,incoming,native_transfer,,,,medium,,\n"
        )
        report = import_wallet_monitors(
            workspace=workspace, uploaded_file=upload(csv_text), created_by=user
        )
        assert report.total_rows == 2
        assert report.created_count == 2
        assert report.failed_count == 0

        treasury = WalletMonitor.objects.get(name="Treasury")
        assert treasury.address == DEMO_WALLET  # checksummed
        assert treasury.event_types == ["erc20_transfer", "native_transfer"]
        assert treasury.tags == ["core", "ops"]
        assert treasury.severity == "high"

    def test_row_level_errors_reported_and_valid_rows_kept(self, workspace, chain, user):
        csv_text = (
            f"{HEADER}\n"
            f"Good,{DEMO_WALLET},testnet,both,native_transfer,,,,medium,,\n"
            f"BadAddress,0x1234,testnet,both,native_transfer,,,,medium,,\n"
            f"BadChain,{OTHER_WALLET},nope,both,native_transfer,,,,medium,,\n"
        )
        report = import_wallet_monitors(
            workspace=workspace, uploaded_file=upload(csv_text), created_by=user
        )
        assert report.created_count == 1
        assert report.failed_count == 2
        rows = {r["row"]: r for r in report.report["rows"]}
        assert rows[2]["status"] == "created"
        assert rows[3]["status"] == "error" and any("address" in e for e in rows[3]["errors"])
        assert rows[4]["status"] == "error" and any("chain" in e for e in rows[4]["errors"])
        assert WalletMonitor.objects.count() == 1

    def test_duplicate_within_file_rejected(self, workspace, chain, user):
        csv_text = (
            f"{HEADER}\n"
            f"One,{DEMO_WALLET},testnet,both,native_transfer,,,,medium,,\n"
            f"Two,{DEMO_WALLET.lower()},testnet,both,native_transfer,,,,medium,,\n"
        )
        report = import_wallet_monitors(
            workspace=workspace, uploaded_file=upload(csv_text), created_by=user
        )
        assert report.created_count == 1
        assert report.failed_count == 1
        errors = [r for r in report.report["rows"] if r["status"] == "error"]
        assert "Duplicate of an earlier row" in errors[0]["errors"][0]

    def test_duplicate_against_database_rejected(self, workspace, chain, user, wallet_monitor):
        csv_text = f"{HEADER}\nCopy,{DEMO_WALLET},testnet,both,native_transfer,,,,medium,,\n"
        report = import_wallet_monitors(
            workspace=workspace, uploaded_file=upload(csv_text), created_by=user
        )
        assert report.created_count == 0
        assert report.failed_count == 1

    def test_missing_required_columns_is_file_error(self, workspace, user):
        with pytest.raises(CsvImportError, match="Missing required column"):
            import_wallet_monitors(
                workspace=workspace,
                uploaded_file=upload("name,foo\nX,1\n"),
                created_by=user,
            )

    def test_too_many_rows_rejected(self, workspace, user, settings):
        settings.CSV_IMPORT_MAX_ROWS = 2
        rows = "\n".join(f"m{i},{DEMO_WALLET},testnet,both,,,,,medium,," for i in range(3))
        with pytest.raises(CsvImportError, match="Too many rows"):
            import_wallet_monitors(
                workspace=workspace, uploaded_file=upload(f"{HEADER}\n{rows}\n"), created_by=user
            )

    def test_oversized_file_rejected(self, workspace, user, settings):
        settings.CSV_IMPORT_MAX_BYTES = 50
        with pytest.raises(CsvImportError, match="too large"):
            import_wallet_monitors(
                workspace=workspace,
                uploaded_file=upload(HEADER + "\n" + "x" * 100),
                created_by=user,
            )

    def test_invalid_rows_never_partially_created(self, workspace, chain, user):
        # min_value_wei invalid → row fails entirely; nothing half-written.
        csv_text = (
            f"{HEADER}\n"
            f"Broken,{DEMO_WALLET},testnet,both,native_transfer,,not-a-number,,medium,,\n"
        )
        report = import_wallet_monitors(
            workspace=workspace, uploaded_file=upload(csv_text), created_by=user
        )
        assert report.created_count == 0
        assert WalletMonitor.objects.count() == 0


class TestImportApi:
    def test_import_endpoint(self, api, workspace, chain):
        csv_text = f"{HEADER}\nApiRow,{DEMO_WALLET},testnet,both,native_transfer,,,,medium,,\n"
        response = api.post(
            f"/api/v1/wallet-monitors/import-csv/?workspace={workspace.pk}",
            {"file": upload(csv_text)},
            format="multipart",
        )
        assert response.status_code == 201, response.content
        assert response.json()["created_count"] == 1

    def test_non_csv_rejected(self, api, workspace):
        bad = SimpleUploadedFile("abi.json", b"[]", content_type="application/json")
        response = api.post(
            f"/api/v1/wallet-monitors/import-csv/?workspace={workspace.pk}",
            {"file": bad},
            format="multipart",
        )
        assert response.status_code == 400


class TestExport:
    def test_export_roundtrip(self, workspace, chain, user, wallet_monitor):
        text = export_wallet_monitors(workspace)
        lines = text.strip().splitlines()
        assert lines[0] == HEADER
        assert DEMO_WALLET in lines[1]
        assert "testnet" in lines[1]

        # A fresh workspace can re-import the exported file untouched.
        from apps.workspaces.services import create_workspace

        clone_ws = create_workspace(name="Clone", owner=user)
        report = import_wallet_monitors(
            workspace=clone_ws, uploaded_file=upload(text), created_by=user
        )
        assert report.created_count == 1
        assert report.failed_count == 0
