"""
Email monitor — watches an IMAP inbox for XML invoice attachments.
Supports Gmail, Outlook, and any standard IMAP provider.
"""
import os
import email
import imaplib
import logging
import time
from email.header import decode_header
from typing import Callable

logger = logging.getLogger(__name__)


class EmailMonitor:
    """Monitors an IMAP mailbox for incoming XML attachments."""

    def __init__(self, host: str, port: int, username: str, password: str,
                 folder: str = "INBOX", xml_save_dir: str = "data/xml_files"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.folder = folder
        self.xml_save_dir = xml_save_dir
        self.connection = None
        os.makedirs(xml_save_dir, exist_ok=True)

    def connect(self):
        """Establish IMAP connection."""
        logger.info(f"Connecting to {self.host}:{self.port}")
        self.connection = imaplib.IMAP4_SSL(self.host, self.port)
        self.connection.login(self.username, self.password)
        logger.info(f"Logged in as {self.username}")

    def disconnect(self):
        """Close the IMAP connection."""
        if self.connection:
            try:
                self.connection.logout()
            except Exception:
                pass
            self.connection = None

    def check_for_new_xml(self, on_xml_found: Callable = None,
                          mark_as_read: bool = True) -> list:
        """
        Check for unread emails with XML attachments.

        Args:
            on_xml_found: Callback function(file_path, sender, subject) for each XML found
            mark_as_read: Whether to mark processed emails as read

        Returns:
            List of saved XML file paths
        """
        if not self.connection:
            self.connect()

        self.connection.select(self.folder)
        # Search for unread emails
        status, messages = self.connection.search(None, "UNSEEN")

        if status != "OK" or not messages[0]:
            logger.debug("No new unread emails")
            return []

        xml_files = []
        message_ids = messages[0].split()
        logger.info(f"Found {len(message_ids)} unread emails")

        for msg_id in message_ids:
            try:
                xml_paths = self._process_email(msg_id, on_xml_found)
                xml_files.extend(xml_paths)

                if mark_as_read and xml_paths:
                    self.connection.store(msg_id, "+FLAGS", "\\Seen")
            except Exception as e:
                logger.error(f"Error processing email {msg_id}: {e}")

        return xml_files

    def _process_email(self, msg_id: bytes, on_xml_found: Callable = None) -> list:
        """Process a single email and extract XML attachments."""
        status, msg_data = self.connection.fetch(msg_id, "(RFC822)")
        if status != "OK":
            return []

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = self._decode_header(msg["Subject"])
        sender = self._decode_header(msg["From"])
        logger.info(f"Processing email from: {sender}, subject: {subject}")

        xml_files = []

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue

            filename = part.get_filename()
            if not filename:
                continue

            filename = self._decode_header(filename)
            if not filename.lower().endswith(".xml"):
                continue

            # Save the XML file
            safe_filename = self._safe_filename(filename)
            file_path = os.path.join(self.xml_save_dir, safe_filename)

            # Avoid overwriting — append timestamp if file exists
            if os.path.exists(file_path):
                base, ext = os.path.splitext(safe_filename)
                file_path = os.path.join(
                    self.xml_save_dir,
                    f"{base}_{int(time.time())}{ext}"
                )

            payload = part.get_payload(decode=True)
            with open(file_path, "wb") as f:
                f.write(payload)

            logger.info(f"Saved XML: {file_path}")
            xml_files.append(file_path)

            if on_xml_found:
                try:
                    on_xml_found(file_path, sender, subject)
                except Exception as e:
                    logger.error(f"Callback error for {file_path}: {e}")

        return xml_files

    def _decode_header(self, value: str) -> str:
        """Decode email header value."""
        if not value:
            return ""
        decoded_parts = decode_header(value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(str(part))
        return " ".join(result)

    def _safe_filename(self, filename: str) -> str:
        """Make a filename safe for saving."""
        keepchars = ("-", "_", ".")
        return "".join(c for c in filename if c.isalnum() or c in keepchars).rstrip()


def start_polling(host: str, port: int, username: str, password: str,
                  folder: str, xml_save_dir: str, poll_interval: int,
                  on_xml_found: Callable = None):
    """
    Start polling the mailbox for new XML attachments.
    This runs in a loop — intended to be called from a background thread or scheduler.
    """
    monitor = EmailMonitor(host, port, username, password, folder, xml_save_dir)

    while True:
        try:
            monitor.connect()
            xml_files = monitor.check_for_new_xml(on_xml_found=on_xml_found)
            if xml_files:
                logger.info(f"Processed {len(xml_files)} XML files")
            monitor.disconnect()
        except Exception as e:
            logger.error(f"Email polling error: {e}")
            monitor.disconnect()

        time.sleep(poll_interval)
