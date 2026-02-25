"""
Parser for Costa Rica Factura Electrónica XML (v4.3 / v4.4)
Extracts all relevant fields for QuickBooks Online Bill creation.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# Namespace patterns for Costa Rica electronic invoices
NAMESPACES_V44 = {
    "fe": "https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/facturaElectronica"
}
NAMESPACES_V43 = {
    "fe": "https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.3/facturaElectronica"
}

# Identification type mapping
ID_TYPES = {
    "01": "Cedula Fisica",
    "02": "Cedula Juridica",
    "03": "DIMEX",
    "04": "NITE",
}

# IVA rate codes
IVA_RATE_CODES = {
    "01": 0,      # Exento
    "02": 1,      # Tarifa reducida 1%
    "03": 2,      # Tarifa reducida 2%
    "04": 4,      # Tarifa reducida 4%
    "05": 0,      # Transitorio 0%
    "06": 4,      # Transitorio 4%
    "07": 8,      # Transitorio 8%
    "08": 13,     # Tarifa general 13%
    "09": 0,      # No sujeto
    "10": 0,      # Exento canasta básica
}


@dataclass
class TaxDetail:
    code: str                    # Tax code (01 = IVA)
    rate_code: str               # IVA rate code
    rate: float                  # Tax rate percentage
    amount: float                # Tax amount


@dataclass
class Discount:
    amount: float
    code: str                    # Discount reason code


@dataclass
class LineItem:
    line_number: int
    cabys_code: str              # CABYS product code
    commercial_code: str         # Commercial code
    commercial_code_type: str    # Commercial code type
    quantity: float
    unit_of_measure: str
    description: str
    unit_price: float
    total_amount: float          # quantity * unit_price
    discount: Optional[Discount]
    subtotal: float              # total_amount - discount
    base_amount: float           # Base for tax calculation
    taxes: list                  # List of TaxDetail
    net_tax: float               # Total tax for this line
    line_total: float            # Final line total


@dataclass
class Party:
    name: str
    id_type: str                 # 01=Fisica, 02=Juridica, etc.
    id_number: str
    province: str = ""
    canton: str = ""
    district: str = ""
    address: str = ""
    phone_country: str = ""
    phone_number: str = ""
    email: str = ""


@dataclass
class OtherCharge:
    doc_type: str
    detail: str
    percentage: float
    amount: float


@dataclass
class InvoiceSummary:
    currency_code: str
    exchange_rate: float
    total_taxed_services: float
    total_exempt_services: float
    total_taxed_goods: float
    total_exempt_goods: float
    total_taxed: float
    total_exempt: float
    total_sales: float
    total_discounts: float
    total_net_sales: float
    total_tax: float
    total_other_charges: float
    total_invoice: float
    payment_method: str


@dataclass
class CostaRicaInvoice:
    clave: str                   # Unique key (50 digits)
    consecutive_number: str      # NumeroConsecutivo
    issue_date: datetime
    issuer: Party                # Emisor (vendor/supplier)
    receiver: Party              # Receptor (buyer/client)
    sale_condition: str          # 01=Cash, 02=Credit, etc.
    activity_code_issuer: str
    activity_code_receiver: str
    line_items: list             # List of LineItem
    other_charges: list          # List of OtherCharge
    summary: InvoiceSummary
    xml_version: str             # v4.3 or v4.4
    raw_xml: str = ""


def _find_namespace(root):
    """Detect the namespace from the root element."""
    tag = root.tag
    if "{" in tag:
        ns = tag.split("}")[0].strip("{")
        if "v4.4" in ns:
            return {"fe": ns}, "v4.4"
        elif "v4.3" in ns:
            return {"fe": ns}, "v4.3"
        else:
            return {"fe": ns}, "unknown"
    return {}, "unknown"


def _text(element, path, ns, default=""):
    """Safely extract text from an XML element."""
    el = element.find(path, ns)
    return el.text.strip() if el is not None and el.text else default


def _float(element, path, ns, default=0.0):
    """Safely extract a float from an XML element."""
    val = _text(element, path, ns, "")
    try:
        return float(val) if val else default
    except ValueError:
        return default


def _parse_party(element, ns):
    """Parse Emisor or Receptor element into a Party dataclass."""
    if element is None:
        return Party(name="", id_type="", id_number="")

    ubicacion = element.find("fe:Ubicacion", ns)
    telefono = element.find("fe:Telefono", ns)

    return Party(
        name=_text(element, "fe:Nombre", ns),
        id_type=_text(element, "fe:Identificacion/fe:Tipo", ns),
        id_number=_text(element, "fe:Identificacion/fe:Numero", ns),
        province=_text(ubicacion, "fe:Provincia", ns) if ubicacion is not None else "",
        canton=_text(ubicacion, "fe:Canton", ns) if ubicacion is not None else "",
        district=_text(ubicacion, "fe:Distrito", ns) if ubicacion is not None else "",
        address=_text(ubicacion, "fe:OtrasSenas", ns) if ubicacion is not None else "",
        phone_country=_text(telefono, "fe:CodigoPais", ns) if telefono is not None else "",
        phone_number=_text(telefono, "fe:NumTelefono", ns) if telefono is not None else "",
        email=_text(element, "fe:CorreoElectronico", ns),
    )


def _parse_line_item(line_el, ns):
    """Parse a single LineaDetalle element."""
    # Parse discount
    desc_el = line_el.find("fe:Descuento", ns)
    discount = None
    if desc_el is not None:
        discount = Discount(
            amount=_float(desc_el, "fe:MontoDescuento", ns),
            code=_text(desc_el, "fe:CodigoDescuento", ns),
        )

    # Parse taxes
    taxes = []
    for tax_el in line_el.findall("fe:Impuesto", ns):
        taxes.append(TaxDetail(
            code=_text(tax_el, "fe:Codigo", ns),
            rate_code=_text(tax_el, "fe:CodigoTarifaIVA", ns),
            rate=_float(tax_el, "fe:Tarifa", ns),
            amount=_float(tax_el, "fe:Monto", ns),
        ))

    return LineItem(
        line_number=int(_text(line_el, "fe:NumeroLinea", ns, "0")),
        cabys_code=_text(line_el, "fe:CodigoCABYS", ns),
        commercial_code=_text(line_el, "fe:CodigoComercial/fe:Codigo", ns),
        commercial_code_type=_text(line_el, "fe:CodigoComercial/fe:Tipo", ns),
        quantity=_float(line_el, "fe:Cantidad", ns),
        unit_of_measure=_text(line_el, "fe:UnidadMedida", ns),
        description=_text(line_el, "fe:Detalle", ns).rstrip("/"),
        unit_price=_float(line_el, "fe:PrecioUnitario", ns),
        total_amount=_float(line_el, "fe:MontoTotal", ns),
        discount=discount,
        subtotal=_float(line_el, "fe:SubTotal", ns),
        base_amount=_float(line_el, "fe:BaseImponible", ns),
        taxes=taxes,
        net_tax=_float(line_el, "fe:ImpuestoNeto", ns),
        line_total=_float(line_el, "fe:MontoTotalLinea", ns),
    )


def _parse_other_charges(root, ns):
    """Parse OtrosCargos elements."""
    charges = []
    for charge_el in root.findall("fe:OtrosCargos", ns):
        charges.append(OtherCharge(
            doc_type=_text(charge_el, "fe:TipoDocumentoOC", ns),
            detail=_text(charge_el, "fe:Detalle", ns),
            percentage=_float(charge_el, "fe:PorcentajeOC", ns),
            amount=_float(charge_el, "fe:MontoCargo", ns),
        ))
    return charges


def _parse_summary(resumen_el, ns):
    """Parse ResumenFactura element."""
    if resumen_el is None:
        raise ValueError("Missing ResumenFactura element")

    currency_el = resumen_el.find("fe:CodigoTipoMoneda", ns)
    payment_el = resumen_el.find("fe:MedioPago", ns)

    return InvoiceSummary(
        currency_code=_text(currency_el, "fe:CodigoMoneda", ns, "CRC") if currency_el is not None else "CRC",
        exchange_rate=_float(currency_el, "fe:TipoCambio", ns, 1.0) if currency_el is not None else 1.0,
        total_taxed_services=_float(resumen_el, "fe:TotalServGravados", ns),
        total_exempt_services=_float(resumen_el, "fe:TotalServExentos", ns),
        total_taxed_goods=_float(resumen_el, "fe:TotalMercanciasGravadas", ns),
        total_exempt_goods=_float(resumen_el, "fe:TotalMercanciasExentas", ns),
        total_taxed=_float(resumen_el, "fe:TotalGravado", ns),
        total_exempt=_float(resumen_el, "fe:TotalExento", ns),
        total_sales=_float(resumen_el, "fe:TotalVenta", ns),
        total_discounts=_float(resumen_el, "fe:TotalDescuentos", ns),
        total_net_sales=_float(resumen_el, "fe:TotalVentaNeta", ns),
        total_tax=_float(resumen_el, "fe:TotalImpuesto", ns),
        total_other_charges=_float(resumen_el, "fe:TotalOtrosCargos", ns),
        total_invoice=_float(resumen_el, "fe:TotalComprobante", ns),
        payment_method=_text(payment_el, "fe:TipoMedioPago", ns) if payment_el is not None else "",
    )


def parse_xml_file(file_path: str) -> CostaRicaInvoice:
    """Parse a Costa Rica electronic invoice XML file."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    return _parse_root(root, file_path=file_path)


def parse_xml_string(xml_content: str) -> CostaRicaInvoice:
    """Parse a Costa Rica electronic invoice from XML string."""
    root = ET.fromstring(xml_content)
    return _parse_root(root, raw_xml=xml_content)


def _parse_root(root, file_path: str = "", raw_xml: str = "") -> CostaRicaInvoice:
    """Parse the root element of a Costa Rica electronic invoice."""
    ns, version = _find_namespace(root)

    if not ns:
        raise ValueError("Could not detect XML namespace. Is this a valid Costa Rica electronic invoice?")

    # Parse issue date
    date_str = _text(root, "fe:FechaEmision", ns)
    try:
        issue_date = datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        issue_date = datetime.now()

    # Parse line items
    detalle_servicio = root.find("fe:DetalleServicio", ns)
    line_items = []
    if detalle_servicio is not None:
        for line_el in detalle_servicio.findall("fe:LineaDetalle", ns):
            line_items.append(_parse_line_item(line_el, ns))

    if file_path and not raw_xml:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_xml = f.read()

    return CostaRicaInvoice(
        clave=_text(root, "fe:Clave", ns),
        consecutive_number=_text(root, "fe:NumeroConsecutivo", ns),
        issue_date=issue_date,
        issuer=_parse_party(root.find("fe:Emisor", ns), ns),
        receiver=_parse_party(root.find("fe:Receptor", ns), ns),
        sale_condition=_text(root, "fe:CondicionVenta", ns),
        activity_code_issuer=_text(root, "fe:CodigoActividadEmisor", ns),
        activity_code_receiver=_text(root, "fe:CodigoActividadReceptor", ns),
        line_items=line_items,
        other_charges=_parse_other_charges(root, ns),
        summary=_parse_summary(root.find("fe:ResumenFactura", ns), ns),
        xml_version=version,
        raw_xml=raw_xml,
    )


def validate_invoice(invoice: CostaRicaInvoice) -> list:
    """Validate the parsed invoice and return a list of issues."""
    issues = []

    if not invoice.clave or len(invoice.clave) != 50:
        issues.append(f"Invalid Clave length: {len(invoice.clave) if invoice.clave else 0} (expected 50)")

    if not invoice.consecutive_number:
        issues.append("Missing NumeroConsecutivo")

    if not invoice.issuer.name:
        issues.append("Missing Emisor name")

    if not invoice.issuer.id_number:
        issues.append("Missing Emisor identification number")

    if not invoice.receiver.name:
        issues.append("Missing Receptor name")

    if not invoice.line_items:
        issues.append("No line items found")

    if invoice.summary.total_invoice <= 0:
        issues.append("Total invoice amount is zero or negative")

    # Verify line totals add up
    calculated_line_total = sum(li.line_total for li in invoice.line_items)
    other_charges_total = sum(oc.amount for oc in invoice.other_charges)
    expected_total = calculated_line_total + other_charges_total
    tolerance = 0.05  # Small tolerance for floating point
    if abs(expected_total - invoice.summary.total_invoice) > tolerance:
        issues.append(
            f"Total mismatch: lines+charges={expected_total:.2f} vs invoice_total={invoice.summary.total_invoice:.2f}"
        )

    return issues
