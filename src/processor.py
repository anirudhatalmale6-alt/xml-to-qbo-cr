"""
Main invoice processing pipeline.
Orchestrates: XML parsing → validation → vendor lookup/create → bill creation.
"""
import os
import logging

from .parsers.cr_invoice_parser import parse_xml_file, parse_xml_string, validate_invoice
from .qbo.client import find_or_create_vendor, create_bill, query_bill_by_doc_number
from .qbo.bill_builder import build_bill_payload
from .database import (
    invoice_exists, save_invoice_record, update_invoice_status, add_log
)

logger = logging.getLogger(__name__)


class ProcessingResult:
    def __init__(self, success: bool, clave: str = "", message: str = "",
                 qbo_bill_id: str = "", qbo_vendor_id: str = ""):
        self.success = success
        self.clave = clave
        self.message = message
        self.qbo_bill_id = qbo_bill_id
        self.qbo_vendor_id = qbo_vendor_id


def process_xml_file(file_path: str, dry_run: bool = False) -> ProcessingResult:
    """
    Process a single XML invoice file end-to-end.

    Args:
        file_path: Path to the XML file
        dry_run: If True, parse and validate only — don't push to QBO

    Returns:
        ProcessingResult with status and details
    """
    filename = os.path.basename(file_path)
    logger.info(f"Processing: {filename}")

    # Step 1: Parse XML
    try:
        invoice = parse_xml_file(file_path)
        logger.info(f"Parsed invoice: {invoice.clave} from {invoice.issuer.name}")
    except Exception as e:
        logger.error(f"Failed to parse {filename}: {e}")
        return ProcessingResult(False, message=f"Parse error: {e}")

    # Step 2: Check for duplicates
    if invoice_exists(invoice.clave):
        msg = f"Invoice already processed: {invoice.clave}"
        logger.warning(msg)
        return ProcessingResult(False, clave=invoice.clave, message=msg)

    # Step 3: Validate
    issues = validate_invoice(invoice)
    if issues:
        msg = f"Validation issues: {'; '.join(issues)}"
        logger.warning(msg)
        # Save record as failed
        save_invoice_record({
            "clave": invoice.clave,
            "consecutive_number": invoice.consecutive_number,
            "issuer_name": invoice.issuer.name,
            "issuer_id": invoice.issuer.id_number,
            "receiver_name": invoice.receiver.name,
            "receiver_id": invoice.receiver.id_number,
            "issue_date": invoice.issue_date.isoformat(),
            "currency": invoice.summary.currency_code,
            "total_amount": invoice.summary.total_invoice,
            "total_tax": invoice.summary.total_tax,
            "xml_filename": filename,
        })
        update_invoice_status(invoice.clave, "error", error_message=msg)
        add_log(invoice.clave, "validate", "error", msg)
        return ProcessingResult(False, clave=invoice.clave, message=msg)

    # Save initial record
    save_invoice_record({
        "clave": invoice.clave,
        "consecutive_number": invoice.consecutive_number,
        "issuer_name": invoice.issuer.name,
        "issuer_id": invoice.issuer.id_number,
        "receiver_name": invoice.receiver.name,
        "receiver_id": invoice.receiver.id_number,
        "issue_date": invoice.issue_date.isoformat(),
        "currency": invoice.summary.currency_code,
        "total_amount": invoice.summary.total_invoice,
        "total_tax": invoice.summary.total_tax,
        "xml_filename": filename,
    })
    add_log(invoice.clave, "parse", "success", f"Parsed {len(invoice.line_items)} lines")

    if dry_run:
        update_invoice_status(invoice.clave, "dry_run")
        add_log(invoice.clave, "dry_run", "success", "Dry run — no QBO push")
        return ProcessingResult(
            True, clave=invoice.clave,
            message=f"Dry run OK: {invoice.issuer.name} - {invoice.summary.total_invoice} {invoice.summary.currency_code}"
        )

    # Step 4: Find or create vendor in QBO
    try:
        vendor = find_or_create_vendor(invoice.issuer)
        vendor_id = vendor["Id"]
        add_log(invoice.clave, "vendor", "success", f"Vendor ID: {vendor_id}")
        logger.info(f"Vendor: {vendor.get('DisplayName')} (ID: {vendor_id})")
    except Exception as e:
        msg = f"Vendor error: {e}"
        logger.error(msg)
        update_invoice_status(invoice.clave, "error", error_message=msg)
        add_log(invoice.clave, "vendor", "error", msg)
        return ProcessingResult(False, clave=invoice.clave, message=msg)

    # Step 5: Check if bill already exists in QBO
    try:
        existing_bill = query_bill_by_doc_number(invoice.consecutive_number)
        if existing_bill:
            msg = f"Bill already exists in QBO with DocNumber {invoice.consecutive_number}"
            logger.warning(msg)
            update_invoice_status(
                invoice.clave, "duplicate",
                qbo_vendor_id=vendor_id,
                qbo_bill_id=existing_bill["Id"],
                error_message=msg
            )
            add_log(invoice.clave, "bill_check", "duplicate", msg)
            return ProcessingResult(
                False, clave=invoice.clave, message=msg,
                qbo_bill_id=existing_bill["Id"], qbo_vendor_id=vendor_id
            )
    except Exception as e:
        logger.warning(f"Could not check for existing bill: {e}")

    # Step 6: Create bill in QBO
    try:
        bill_payload = build_bill_payload(invoice, vendor_id)
        bill = create_bill(bill_payload)
        bill_id = bill["Id"] if isinstance(bill, dict) else str(bill)
        update_invoice_status(
            invoice.clave, "success",
            qbo_vendor_id=vendor_id,
            qbo_bill_id=bill_id
        )
        add_log(invoice.clave, "bill_create", "success", f"Bill ID: {bill_id}")
        logger.info(f"Created bill {bill_id} for {invoice.issuer.name}")
        return ProcessingResult(
            True, clave=invoice.clave,
            message=f"Bill created: {invoice.issuer.name} - {invoice.summary.total_invoice} {invoice.summary.currency_code}",
            qbo_bill_id=bill_id, qbo_vendor_id=vendor_id
        )
    except Exception as e:
        msg = f"Bill creation error: {e}"
        logger.error(msg)
        update_invoice_status(
            invoice.clave, "error",
            qbo_vendor_id=vendor_id,
            error_message=msg
        )
        add_log(invoice.clave, "bill_create", "error", msg)
        return ProcessingResult(
            False, clave=invoice.clave, message=msg, qbo_vendor_id=vendor_id
        )


def process_directory(directory: str, dry_run: bool = False) -> list:
    """Process all XML files in a directory."""
    results = []
    if not os.path.isdir(directory):
        logger.error(f"Directory not found: {directory}")
        return results

    xml_files = [f for f in os.listdir(directory) if f.lower().endswith(".xml")]
    logger.info(f"Found {len(xml_files)} XML files in {directory}")

    for filename in sorted(xml_files):
        file_path = os.path.join(directory, filename)
        result = process_xml_file(file_path, dry_run=dry_run)
        results.append(result)

    return results
