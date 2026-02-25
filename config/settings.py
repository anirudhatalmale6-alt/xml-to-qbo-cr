"""
Application settings — loaded from environment variables or .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()


# QuickBooks Online
QBO_CLIENT_ID = os.getenv("QBO_CLIENT_ID", "")
QBO_CLIENT_SECRET = os.getenv("QBO_CLIENT_SECRET", "")
QBO_REDIRECT_URI = os.getenv("QBO_REDIRECT_URI", "http://localhost:5000/qbo/callback")
QBO_ENVIRONMENT = os.getenv("QBO_ENVIRONMENT", "sandbox")  # "sandbox" or "production"
QBO_COMPANY_ID = os.getenv("QBO_COMPANY_ID", "")

# QBO API base URLs
QBO_BASE_URL_SANDBOX = "https://sandbox-quickbooks.api.intuit.com"
QBO_BASE_URL_PRODUCTION = "https://quickbooks.api.intuit.com"

# OAuth 2.0 endpoints
QBO_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QBO_REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"

# Email (IMAP)
EMAIL_HOST = os.getenv("EMAIL_HOST", "imap.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "993"))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")  # App password for Gmail
EMAIL_FOLDER = os.getenv("EMAIL_FOLDER", "INBOX")
EMAIL_POLL_INTERVAL_SECONDS = int(os.getenv("EMAIL_POLL_INTERVAL_SECONDS", "60"))

# Application
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "change-me-in-production")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/app.db")
XML_STORAGE_PATH = os.getenv("XML_STORAGE_PATH", "data/xml_files")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Dashboard
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
