"""
Converts a parsed Costa Rica electronic invoice into a QBO Bill payload.
Uses proper international tax handling (non-US locale).
"""
import logging
from ..parsers.cr_invoice_parser import CostaRicaInvoice, LineItem

logger = logging.getLogger(__name__)

# Default expense account — should be configured per-company
DEFAULT_EXPENSE_ACCOUNT_REF = {"value": "7", "name": "Expenses"}


def build_bill_payload(
    invoice: CostaRicaInvoice,
    vendor_id: str,
    expense_account_ref: dict = None,
    tax_code_ref: str = None,
    exempt_tax_code_ref: str = None,
) -> dict:
    """
    Build a QBO Bill JSON payload from a parsed Costa Rica invoice.

    For international (non-US) QBO companies, tax_code_ref and exempt_tax_code_ref
    should be the actual TaxCode IDs from the company (queried via SELECT * FROM TaxCode).
    Do NOT use US-specific "TAX"/"NON" values.

    Args:
        invoice: Parsed CostaRicaInvoice object
        vendor_id: QBO Vendor ID
        expense_account_ref: QBO Account reference for expense lines
        tax_code_ref: QBO TaxCode ID for taxable lines (query from company)
        exempt_tax_code_ref: QBO TaxCode ID for exempt lines (query from company)
    """
    if expense_account_ref is None:
        expense_account_ref = DEFAULT_EXPENSE_ACCOUNT_REF

    lines = []
    line_num = 1
    total_taxable_amount = 0.0
    total_tax_amount = 0.0

    for item in invoice.line_items:
        # Skip separator/zero-value lines
        if item.unit_price <= 0.01 and item.line_total < 0.01:
            logger.debug(f"Skipping zero-value line: {item.description}")
            continue

        # Determine if this line is taxable
        is_taxable = any(t.rate > 0 for t in item.taxes)
        line_tax_code = tax_code_ref if is_taxable else exempt_tax_code_ref

        # Calculate net amount (subtotal after discount, before tax)
        net_amount = item.subtotal
        if is_taxable:
            total_taxable_amount += net_amount
            total_tax_amount += item.net_tax

        line_detail = {
            "AccountRef": expense_account_ref,
            "BillableStatus": "NotBillable",
        }
        if line_tax_code:
            line_detail["TaxCodeRef"] = {"value": line_tax_code}

        bill_line = {
            "DetailType": "AccountBasedExpenseLineDetail",
            "Amount": round(net_amount, 2),
            "Description": f"{item.description} (x{int(item.quantity)})" if item.quantity > 1 else item.description,
            "AccountBasedExpenseLineDetail": line_detail,
            "LineNum": line_num,
        }
        lines.append(bill_line)
        line_num += 1

    # Add other charges (e.g., service charge) as separate line
    for charge in invoice.other_charges:
        if charge.amount > 0:
            charge_detail = {
                "AccountRef": expense_account_ref,
                "BillableStatus": "NotBillable",
            }
            if exempt_tax_code_ref:
                charge_detail["TaxCodeRef"] = {"value": exempt_tax_code_ref}

            bill_line = {
                "DetailType": "AccountBasedExpenseLineDetail",
                "Amount": round(charge.amount, 2),
                "Description": f"{charge.detail} ({charge.percentage}%)",
                "AccountBasedExpenseLineDetail": charge_detail,
                "LineNum": line_num,
            }
            lines.append(bill_line)
            line_num += 1

    bill_payload = {
        "VendorRef": {"value": vendor_id},
        "TxnDate": invoice.issue_date.strftime("%Y-%m-%d"),
        "DocNumber": invoice.consecutive_number,
        "Line": lines,
        "GlobalTaxCalculation": "TaxExcluded",
        "PrivateNote": f"Clave: {invoice.clave} | Auto-imported from XML",
    }

    # Add explicit tax detail with override to match the XML amounts exactly
    if total_tax_amount > 0:
        bill_payload["TxnTaxDetail"] = {
            "TotalTax": round(total_tax_amount, 2),
        }

    # Set currency
    if invoice.summary.currency_code:
        bill_payload["CurrencyRef"] = {
            "value": invoice.summary.currency_code,
        }
        if invoice.summary.exchange_rate and invoice.summary.exchange_rate != 1:
            bill_payload["ExchangeRate"] = invoice.summary.exchange_rate

    return bill_payload


def calculate_expected_total(invoice: CostaRicaInvoice) -> float:
    """Calculate expected bill total for verification."""
    line_subtotals = sum(
        item.subtotal for item in invoice.line_items
        if item.unit_price > 0.01 or item.line_total >= 0.01
    )
    taxes = sum(
        item.net_tax for item in invoice.line_items
        if item.unit_price > 0.01 or item.line_total >= 0.01
    )
    other_charges = sum(c.amount for c in invoice.other_charges)
    return round(line_subtotals + taxes + other_charges, 2)
