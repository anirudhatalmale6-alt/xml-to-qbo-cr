"""
Main entry point for XML-to-QBO invoice automation.
Starts the dashboard web server and email polling in background.
"""
import os
import sys
import logging
import threading

from config.settings import (
    EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD,
    EMAIL_FOLDER, EMAIL_POLL_INTERVAL_SECONDS,
    XML_STORAGE_PATH, DASHBOARD_HOST, DASHBOARD_PORT, LOG_LEVEL
)
from src.database import init_db
from src.processor import process_xml_file
from src.email.monitor import EmailMonitor

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/app.log", mode="a"),
    ]
)
logger = logging.getLogger(__name__)


def on_xml_received(file_path: str, sender: str, subject: str):
    """Callback when a new XML is extracted from email."""
    logger.info(f"New XML from {sender}: {os.path.basename(file_path)} (subject: {subject})")
    result = process_xml_file(file_path)
    if result.success:
        logger.info(f"SUCCESS: {result.message}")
    else:
        logger.warning(f"FAILED: {result.message}")


def start_email_monitor():
    """Start email monitoring in a background thread."""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logger.warning("Email credentials not configured — email monitoring disabled.")
        logger.info("Set EMAIL_USER and EMAIL_PASSWORD in .env to enable.")
        return

    xml_dir = os.path.join(os.path.dirname(__file__), XML_STORAGE_PATH)
    os.makedirs(xml_dir, exist_ok=True)

    def polling_loop():
        monitor = EmailMonitor(
            host=EMAIL_HOST,
            port=EMAIL_PORT,
            username=EMAIL_USER,
            password=EMAIL_PASSWORD,
            folder=EMAIL_FOLDER,
            xml_save_dir=xml_dir,
        )
        while True:
            try:
                monitor.connect()
                xml_files = monitor.check_for_new_xml(on_xml_found=on_xml_received)
                if xml_files:
                    logger.info(f"Processed {len(xml_files)} XML files from email")
                monitor.disconnect()
            except Exception as e:
                logger.error(f"Email monitor error: {e}")
                monitor.disconnect()

            import time
            time.sleep(EMAIL_POLL_INTERVAL_SECONDS)

    thread = threading.Thread(target=polling_loop, daemon=True)
    thread.start()
    logger.info(f"Email monitor started — checking every {EMAIL_POLL_INTERVAL_SECONDS}s")


def main():
    """Main application entry point."""
    # Ensure data directories exist
    os.makedirs("data", exist_ok=True)
    os.makedirs(XML_STORAGE_PATH, exist_ok=True)

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Start email monitoring
    start_email_monitor()

    # Start web dashboard
    logger.info(f"Starting dashboard at http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    from src.dashboard.app import app
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    main()
