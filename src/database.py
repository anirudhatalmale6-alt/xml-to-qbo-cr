"""
SQLite database for tracking processed invoices and their status.
"""
import os
import sqlite3
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")


def _get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS processed_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clave TEXT UNIQUE NOT NULL,
            consecutive_number TEXT,
            issuer_name TEXT,
            issuer_id TEXT,
            receiver_name TEXT,
            receiver_id TEXT,
            issue_date TEXT,
            currency TEXT,
            total_amount REAL,
            total_tax REAL,
            qbo_vendor_id TEXT,
            qbo_bill_id TEXT,
            status TEXT DEFAULT 'pending',
            error_message TEXT,
            xml_filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS processing_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_clave TEXT,
            action TEXT,
            status TEXT,
            detail TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_invoices_clave ON processed_invoices(clave);
        CREATE INDEX IF NOT EXISTS idx_invoices_status ON processed_invoices(status);
        CREATE INDEX IF NOT EXISTS idx_log_clave ON processing_log(invoice_clave);
    """)
    conn.commit()
    conn.close()


def invoice_exists(clave: str) -> bool:
    """Check if an invoice has already been processed."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id FROM processed_invoices WHERE clave = ?", (clave,)
    ).fetchone()
    conn.close()
    return row is not None


def save_invoice_record(invoice_data: dict) -> int:
    """Save a new invoice record. Returns the record ID."""
    conn = _get_db()
    cursor = conn.execute("""
        INSERT INTO processed_invoices
        (clave, consecutive_number, issuer_name, issuer_id, receiver_name, receiver_id,
         issue_date, currency, total_amount, total_tax, status, xml_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        invoice_data["clave"],
        invoice_data.get("consecutive_number", ""),
        invoice_data.get("issuer_name", ""),
        invoice_data.get("issuer_id", ""),
        invoice_data.get("receiver_name", ""),
        invoice_data.get("receiver_id", ""),
        invoice_data.get("issue_date", ""),
        invoice_data.get("currency", "CRC"),
        invoice_data.get("total_amount", 0),
        invoice_data.get("total_tax", 0),
        "pending",
        invoice_data.get("xml_filename", ""),
    ))
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id


def update_invoice_status(clave: str, status: str, qbo_vendor_id: str = None,
                          qbo_bill_id: str = None, error_message: str = None):
    """Update the status of a processed invoice."""
    conn = _get_db()
    updates = ["status = ?", "updated_at = ?"]
    params = [status, datetime.now().isoformat()]

    if qbo_vendor_id:
        updates.append("qbo_vendor_id = ?")
        params.append(qbo_vendor_id)
    if qbo_bill_id:
        updates.append("qbo_bill_id = ?")
        params.append(qbo_bill_id)
    if error_message:
        updates.append("error_message = ?")
        params.append(error_message)

    params.append(clave)
    conn.execute(
        f"UPDATE processed_invoices SET {', '.join(updates)} WHERE clave = ?",
        params
    )
    conn.commit()
    conn.close()


def add_log(invoice_clave: str, action: str, status: str, detail: str = ""):
    """Add a processing log entry."""
    conn = _get_db()
    conn.execute("""
        INSERT INTO processing_log (invoice_clave, action, status, detail)
        VALUES (?, ?, ?, ?)
    """, (invoice_clave, action, status, detail))
    conn.commit()
    conn.close()


def get_all_invoices(limit: int = 100, offset: int = 0) -> list:
    """Get all processed invoices for the dashboard."""
    conn = _get_db()
    rows = conn.execute("""
        SELECT * FROM processed_invoices
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_invoice_logs(clave: str) -> list:
    """Get processing logs for a specific invoice."""
    conn = _get_db()
    rows = conn.execute("""
        SELECT * FROM processing_log
        WHERE invoice_clave = ?
        ORDER BY created_at ASC
    """, (clave,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stats() -> dict:
    """Get processing statistics for the dashboard."""
    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) FROM processed_invoices").fetchone()[0]
    success = conn.execute("SELECT COUNT(*) FROM processed_invoices WHERE status = 'success'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM processed_invoices WHERE status = 'error'").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM processed_invoices WHERE status = 'pending'").fetchone()[0]
    total_amount = conn.execute("SELECT COALESCE(SUM(total_amount), 0) FROM processed_invoices WHERE status = 'success'").fetchone()[0]
    conn.close()
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "pending": pending,
        "total_amount": round(total_amount, 2),
    }


# Initialize DB on import
init_db()
