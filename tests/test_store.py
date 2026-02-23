"""Tests for store: insert, get_all_leads, export_csv."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from leadfinder.store import LeadStore


def test_store_insert_and_get():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LeadStore(path)
        store.init_schema()
        store.insert_lead(
            "Acme", "acme.com", "form", "https://acme.com/contact",
            "Contact", 70, "https://acme.com", "Form", None,
        )
        leads = store.get_all_leads()
        assert len(leads) == 1
        assert leads[0]["company_name"] == "Acme"
        assert leads[0]["contact_route_type"] == "form"
        assert leads[0]["confidence"] == 70
        assert "discovered_at" in leads[0]
    finally:
        Path(path).unlink(missing_ok=True)


def test_store_export_csv():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = f.name
    try:
        store = LeadStore(db_path)
        store.init_schema()
        store.insert_lead("B", "b.com", "email", "press@b.com", "Press", 82, "https://b.com", "snippet", None)
        n = store.export_csv(csv_path)
        assert n == 1
        content = Path(csv_path).read_text()
        assert "company_name" in content
        assert "press@b.com" in content
    finally:
        Path(db_path).unlink(missing_ok=True)
        Path(csv_path).unlink(missing_ok=True)
