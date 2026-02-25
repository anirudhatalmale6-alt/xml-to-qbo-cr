"""Tests for the Costa Rica invoice XML parser."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.parsers.cr_invoice_parser import parse_xml_file, validate_invoice


SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_xml")


def test_parse_sample_invoice():
    """Test parsing the sample invoice XML."""
    xml_path = os.path.join(SAMPLE_DIR, "sample_invoice_01.xml")
    invoice = parse_xml_file(xml_path)

    # Basic fields
    assert invoice.clave == "50620022600310121801100100001010000004395188880000"
    assert invoice.consecutive_number == "00100001010000004395"
    assert invoice.xml_version == "v4.4"

    # Issuer (Emisor)
    assert invoice.issuer.name == "PADRE GALLO S. A."
    assert invoice.issuer.id_type == "02"  # Cedula Juridica
    assert invoice.issuer.id_number == "3101218011"
    assert invoice.issuer.email == "padregallopagos@gmail.com"

    # Receiver (Receptor)
    assert invoice.receiver.name == "puro beach srl"
    assert invoice.receiver.id_type == "02"
    assert invoice.receiver.id_number == "3102788357"

    # Line items
    assert len(invoice.line_items) == 27
    assert invoice.line_items[0].description == "Flan de la Casa"
    assert invoice.line_items[0].unit_price == 4000
    assert invoice.line_items[0].quantity == 1
    assert invoice.line_items[0].taxes[0].rate == 13
    assert invoice.line_items[0].line_total == 4068

    # Other charges (service 10%)
    assert len(invoice.other_charges) == 1
    assert invoice.other_charges[0].percentage == 10
    assert invoice.other_charges[0].amount == 18945

    # Summary
    assert invoice.summary.currency_code == "CRC"
    assert invoice.summary.exchange_rate == 1
    assert abs(invoice.summary.total_invoice - 233023.50292) < 0.01
    assert abs(invoice.summary.total_tax - 24628.50012) < 0.01
    assert invoice.summary.payment_method == "06"

    print("✓ All basic fields parsed correctly")


def test_validate_sample_invoice():
    """Test validation of the sample invoice."""
    xml_path = os.path.join(SAMPLE_DIR, "sample_invoice_01.xml")
    invoice = parse_xml_file(xml_path)
    issues = validate_invoice(invoice)

    if issues:
        print(f"Validation issues: {issues}")
    else:
        print("✓ Invoice validation passed — no issues found")

    assert len(issues) == 0, f"Expected no issues, got: {issues}"


def test_line_items_detail():
    """Test detailed line item parsing."""
    xml_path = os.path.join(SAMPLE_DIR, "sample_invoice_01.xml")
    invoice = parse_xml_file(xml_path)

    # Check line 6: Carne Braseada (qty 2)
    line6 = invoice.line_items[5]
    assert line6.description == "Carne Braseada"
    assert line6.quantity == 2
    assert line6.unit_price == 9900
    assert line6.total_amount == 19800
    assert line6.discount.amount == 1980
    assert line6.subtotal == 17820
    assert line6.net_tax == 2316.6
    assert line6.line_total == 20136.6

    # Check line 11: Stop Allergy (zero-priced item)
    line11 = invoice.line_items[10]
    assert line11.description == "Stop Allergy"
    assert line11.unit_price == 0.001
    assert line11.taxes[0].rate == 0  # Exempt

    print("✓ Line item details verified correctly")


def test_invoice_date():
    """Test date parsing."""
    xml_path = os.path.join(SAMPLE_DIR, "sample_invoice_01.xml")
    invoice = parse_xml_file(xml_path)

    assert invoice.issue_date.year == 2026
    assert invoice.issue_date.month == 2
    assert invoice.issue_date.day == 20

    print("✓ Date parsing correct")


if __name__ == "__main__":
    test_parse_sample_invoice()
    test_validate_sample_invoice()
    test_line_items_detail()
    test_invoice_date()
    print("\n✅ All parser tests passed!")
