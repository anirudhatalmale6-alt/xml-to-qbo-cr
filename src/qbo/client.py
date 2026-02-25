"""
QuickBooks Online API client.
Handles Bill creation, Vendor management, and querying.
"""
import requests
import logging

from .auth import get_access_token, get_realm_id
from config.settings import QBO_ENVIRONMENT, QBO_BASE_URL_SANDBOX, QBO_BASE_URL_PRODUCTION

logger = logging.getLogger(__name__)


def _base_url():
    if QBO_ENVIRONMENT == "production":
        return QBO_BASE_URL_PRODUCTION
    return QBO_BASE_URL_SANDBOX


def _api_url(endpoint: str) -> str:
    realm_id = get_realm_id()
    return f"{_base_url()}/v3/company/{realm_id}/{endpoint}"


def _headers():
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _handle_response(response):
    """Handle QBO API response and raise on errors."""
    if response.status_code in (200, 201):
        return response.json()
    logger.error(f"QBO API error {response.status_code}: {response.text}")
    response.raise_for_status()


# --- Vendor Operations ---

def query_vendor_by_name(display_name: str) -> dict:
    """Search for a vendor by display name."""
    # Escape single quotes in name
    safe_name = display_name.replace("'", "\\'")
    query = f"SELECT * FROM Vendor WHERE DisplayName = '{safe_name}'"
    response = requests.get(
        _api_url("query"),
        headers=_headers(),
        params={"query": query},
    )
    data = _handle_response(response)
    vendors = data.get("QueryResponse", {}).get("Vendor", [])
    return vendors[0] if vendors else None


def query_vendor_by_tax_id(tax_id: str) -> dict:
    """Search for a vendor by tax identifier (Costa Rica cédula)."""
    # QBO stores tax ID in TaxIdentifier field for some regions,
    # but we may need to search by AcctNum or a custom field
    query = f"SELECT * FROM Vendor WHERE AcctNum = '{tax_id}'"
    response = requests.get(
        _api_url("query"),
        headers=_headers(),
        params={"query": query},
    )
    data = _handle_response(response)
    vendors = data.get("QueryResponse", {}).get("Vendor", [])
    return vendors[0] if vendors else None


def create_vendor(vendor_data: dict) -> dict:
    """Create a new vendor in QBO."""
    response = requests.post(
        _api_url("vendor"),
        headers=_headers(),
        json=vendor_data,
    )
    data = _handle_response(response)
    return data.get("Vendor", data)


def find_or_create_vendor(issuer) -> dict:
    """Find an existing vendor or create one from invoice issuer data."""
    # First try to find by tax ID (stored as AcctNum)
    vendor = query_vendor_by_tax_id(issuer.id_number)
    if vendor:
        logger.info(f"Found existing vendor: {vendor['DisplayName']} (ID: {vendor['Id']})")
        return vendor

    # Try by display name
    vendor = query_vendor_by_name(issuer.name)
    if vendor:
        logger.info(f"Found existing vendor by name: {vendor['DisplayName']} (ID: {vendor['Id']})")
        return vendor

    # Create new vendor
    logger.info(f"Creating new vendor: {issuer.name}")
    vendor_data = {
        "DisplayName": issuer.name,
        "CompanyName": issuer.name,
        "AcctNum": issuer.id_number,  # Store cédula as account number
        "PrimaryPhone": {
            "FreeFormNumber": f"+{issuer.phone_country}{issuer.phone_number}"
        } if issuer.phone_number else None,
        "PrimaryEmailAddr": {
            "Address": issuer.email
        } if issuer.email else None,
    }
    # Remove None values
    vendor_data = {k: v for k, v in vendor_data.items() if v is not None}

    if issuer.address:
        vendor_data["BillAddr"] = {
            "Line1": issuer.address,
            "Country": "CR",
        }

    return create_vendor(vendor_data)


# --- Bill Operations ---

def create_bill(bill_data: dict) -> dict:
    """Create a bill (vendor invoice) in QBO."""
    response = requests.post(
        _api_url("bill"),
        headers=_headers(),
        json=bill_data,
    )
    data = _handle_response(response)
    return data.get("Bill", data)


def query_bill_by_doc_number(doc_number: str) -> dict:
    """Check if a bill already exists with this document number."""
    safe_num = doc_number.replace("'", "\\'")
    query = f"SELECT * FROM Bill WHERE DocNumber = '{safe_num}'"
    response = requests.get(
        _api_url("query"),
        headers=_headers(),
        params={"query": query},
    )
    data = _handle_response(response)
    bills = data.get("QueryResponse", {}).get("Bill", [])
    return bills[0] if bills else None


# --- Tax Code Operations ---

def get_tax_codes() -> list:
    """Retrieve all tax codes from QBO."""
    query = "SELECT * FROM TaxCode"
    response = requests.get(
        _api_url("query"),
        headers=_headers(),
        params={"query": query},
    )
    data = _handle_response(response)
    return data.get("QueryResponse", {}).get("TaxCode", [])


def get_tax_rates() -> list:
    """Retrieve all tax rates from QBO."""
    query = "SELECT * FROM TaxRate"
    response = requests.get(
        _api_url("query"),
        headers=_headers(),
        params={"query": query},
    )
    data = _handle_response(response)
    return data.get("QueryResponse", {}).get("TaxRate", [])


# --- Account Operations ---

def get_expense_accounts() -> list:
    """Get expense accounts for bill line items."""
    query = "SELECT * FROM Account WHERE AccountType = 'Expense'"
    response = requests.get(
        _api_url("query"),
        headers=_headers(),
        params={"query": query},
    )
    data = _handle_response(response)
    return data.get("QueryResponse", {}).get("Account", [])


def get_accounts_payable() -> list:
    """Get Accounts Payable accounts."""
    query = "SELECT * FROM Account WHERE AccountType = 'Accounts Payable'"
    response = requests.get(
        _api_url("query"),
        headers=_headers(),
        params={"query": query},
    )
    data = _handle_response(response)
    return data.get("QueryResponse", {}).get("Account", [])


# --- Currency Operations ---

def get_preferences() -> dict:
    """Get company preferences (includes multi-currency setting)."""
    response = requests.get(
        _api_url("preferences"),
        headers=_headers(),
    )
    return _handle_response(response)
