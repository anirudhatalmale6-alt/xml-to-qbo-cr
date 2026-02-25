"""
Flask web dashboard for monitoring invoice processing
and managing QBO OAuth connection.
"""
import os
import sys
import secrets
import logging

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config.settings import (
    APP_SECRET_KEY, DASHBOARD_HOST, DASHBOARD_PORT, XML_STORAGE_PATH
)
from src.database import get_all_invoices, get_invoice_logs, get_stats, init_db
from src.qbo.auth import (
    get_authorization_url, exchange_code_for_tokens,
    is_authenticated, get_realm_id
)
from src.processor import process_xml_file, process_directory

logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))
app.secret_key = APP_SECRET_KEY


# --- Dashboard Routes ---

@app.route("/")
def index():
    """Main dashboard page."""
    stats = get_stats()
    invoices = get_all_invoices(limit=50)
    qbo_connected = is_authenticated()
    return render_template("index.html", stats=stats, invoices=invoices,
                           qbo_connected=qbo_connected)


@app.route("/invoices")
def invoices_list():
    """List all processed invoices with pagination."""
    page = int(request.args.get("page", 1))
    per_page = 25
    offset = (page - 1) * per_page
    invoices = get_all_invoices(limit=per_page, offset=offset)
    stats = get_stats()
    return render_template("invoices.html", invoices=invoices, stats=stats,
                           page=page, per_page=per_page)


@app.route("/invoice/<clave>")
def invoice_detail(clave):
    """View details and logs for a specific invoice."""
    logs = get_invoice_logs(clave)
    invoices = get_all_invoices(limit=1000)
    invoice = next((i for i in invoices if i["clave"] == clave), None)
    return render_template("invoice_detail.html", invoice=invoice, logs=logs)


# --- Upload Routes ---

@app.route("/upload", methods=["GET", "POST"])
def upload():
    """Manual XML upload page."""
    if request.method == "POST":
        files = request.files.getlist("xml_files")
        if not files:
            flash("No files selected", "error")
            return redirect(url_for("upload"))

        results = []
        xml_dir = os.path.join(os.path.dirname(__file__), "..", "..", XML_STORAGE_PATH)
        os.makedirs(xml_dir, exist_ok=True)

        for f in files:
            if f.filename and f.filename.lower().endswith(".xml"):
                filename = secure_filename(f.filename)
                file_path = os.path.join(xml_dir, filename)
                f.save(file_path)

                dry_run = not is_authenticated()
                result = process_xml_file(file_path, dry_run=dry_run)
                status = "success" if result.success else "error"
                results.append({
                    "filename": filename,
                    "status": status,
                    "message": result.message,
                })

        for r in results:
            flash(f"{r['filename']}: {r['message']}", r["status"])

        return redirect(url_for("index"))

    return render_template("upload.html")


# --- QBO Auth Routes ---

@app.route("/qbo/auth")
def qbo_auth():
    """Initiate QBO OAuth flow."""
    state = secrets.token_urlsafe(16)
    auth_url = get_authorization_url(state)
    return redirect(auth_url)


@app.route("/qbo/callback")
def qbo_callback():
    """Handle QBO OAuth callback."""
    code = request.args.get("code")
    realm_id = request.args.get("realmId")
    error = request.args.get("error")

    if error:
        flash(f"QBO authorization error: {error}", "error")
        return redirect(url_for("index"))

    if not code or not realm_id:
        flash("Missing authorization code or realm ID", "error")
        return redirect(url_for("index"))

    try:
        exchange_code_for_tokens(code, realm_id)
        flash("Successfully connected to QuickBooks Online!", "success")
    except Exception as e:
        flash(f"Failed to connect: {e}", "error")

    return redirect(url_for("index"))


@app.route("/qbo/status")
def qbo_status():
    """Check QBO connection status."""
    return jsonify({
        "connected": is_authenticated(),
        "realm_id": get_realm_id() if is_authenticated() else None,
    })


# --- API Routes ---

@app.route("/api/process", methods=["POST"])
def api_process():
    """API endpoint to process an XML file."""
    if "xml_file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["xml_file"]
    if not f.filename.lower().endswith(".xml"):
        return jsonify({"error": "File must be XML"}), 400

    xml_dir = os.path.join(os.path.dirname(__file__), "..", "..", XML_STORAGE_PATH)
    os.makedirs(xml_dir, exist_ok=True)
    filename = secure_filename(f.filename)
    file_path = os.path.join(xml_dir, filename)
    f.save(file_path)

    dry_run = not is_authenticated()
    result = process_xml_file(file_path, dry_run=dry_run)

    return jsonify({
        "success": result.success,
        "clave": result.clave,
        "message": result.message,
        "qbo_bill_id": result.qbo_bill_id,
        "qbo_vendor_id": result.qbo_vendor_id,
    })


@app.route("/api/stats")
def api_stats():
    """API endpoint for dashboard stats."""
    return jsonify(get_stats())


# --- Initialize ---

init_db()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=True)
