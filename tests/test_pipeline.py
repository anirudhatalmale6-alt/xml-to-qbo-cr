"""Test the full processing pipeline in dry-run mode."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import init_db, get_all_invoices, get_stats
from src.processor import process_xml_file

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_xml")


def test_dry_run_pipeline():
    """Test processing an XML file in dry-run mode (no QBO calls)."""
    init_db()

    xml_path = os.path.join(SAMPLE_DIR, "sample_invoice_01.xml")
    result = process_xml_file(xml_path, dry_run=True)

    print(f"Success: {result.success}")
    print(f"Clave: {result.clave}")
    print(f"Message: {result.message}")

    assert result.success, f"Pipeline failed: {result.message}"
    assert result.clave == "50620022600310121801100100001010000004395188880000"
    assert "PADRE GALLO" in result.message

    # Check database
    invoices = get_all_invoices()
    assert len(invoices) >= 1
    inv = invoices[0]
    assert inv["issuer_name"] == "PADRE GALLO S. A."
    assert inv["status"] == "dry_run"
    assert abs(inv["total_amount"] - 233023.50292) < 0.01

    stats = get_stats()
    print(f"\nStats: {stats}")
    assert stats["total"] >= 1

    print("\n✅ Full pipeline dry-run test passed!")


def test_duplicate_detection():
    """Test that the same invoice is rejected on second processing."""
    result = process_xml_file(
        os.path.join(SAMPLE_DIR, "sample_invoice_01.xml"),
        dry_run=True
    )

    assert not result.success
    assert "already processed" in result.message.lower()
    print("✅ Duplicate detection works!")


if __name__ == "__main__":
    test_dry_run_pipeline()
    test_duplicate_detection()
    print("\n✅ All pipeline tests passed!")
