"""
Tax code discovery and setup for QBO.
Queries the company's existing tax codes and maps CR tax rates to them.
"""
import logging
import json
import os
from .client import get_tax_codes, get_tax_rates

logger = logging.getLogger(__name__)

TAX_MAPPING_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "tax_mapping.json")


def discover_tax_codes() -> dict:
    """
    Query QBO for existing tax codes and build a mapping.
    Returns dict with 'taxable' and 'exempt' tax code IDs.
    """
    tax_codes = get_tax_codes()
    mapping = {
        "taxable_code_id": None,
        "exempt_code_id": None,
        "all_codes": [],
    }

    for tc in tax_codes:
        code_info = {
            "id": tc["Id"],
            "name": tc.get("Name", ""),
            "active": tc.get("Active", True),
            "taxable": tc.get("Taxable", False),
        }
        mapping["all_codes"].append(code_info)

        if tc.get("Active") and tc.get("Taxable"):
            # Look for IVA 13% or similar
            name = tc.get("Name", "").upper()
            if "13" in name or "IVA" in name or "GENERAL" in name:
                mapping["taxable_code_id"] = tc["Id"]
            elif not mapping["taxable_code_id"]:
                mapping["taxable_code_id"] = tc["Id"]

        if tc.get("Active") and not tc.get("Taxable", True):
            if not mapping["exempt_code_id"]:
                mapping["exempt_code_id"] = tc["Id"]

    # Save mapping for reuse
    os.makedirs(os.path.dirname(TAX_MAPPING_FILE), exist_ok=True)
    with open(TAX_MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)

    logger.info(f"Tax mapping: taxable={mapping['taxable_code_id']}, exempt={mapping['exempt_code_id']}")
    return mapping


def get_tax_mapping() -> dict:
    """Load cached tax mapping or discover fresh."""
    if os.path.exists(TAX_MAPPING_FILE):
        with open(TAX_MAPPING_FILE, "r") as f:
            return json.load(f)
    return discover_tax_codes()
