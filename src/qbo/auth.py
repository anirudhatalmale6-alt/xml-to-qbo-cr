"""
QuickBooks Online OAuth 2.0 authentication handler.
Manages authorization flow, token storage, and token refresh.
"""
import os
import json
import time
import requests
import base64
from urllib.parse import urlencode

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import (
    QBO_CLIENT_ID, QBO_CLIENT_SECRET, QBO_REDIRECT_URI,
    QBO_AUTH_URL, QBO_TOKEN_URL, QBO_REVOKE_URL
)

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "qbo_tokens.json")


def get_authorization_url(state: str = "random_state") -> str:
    """Generate the OAuth 2.0 authorization URL for QBO."""
    params = {
        "client_id": QBO_CLIENT_ID,
        "response_type": "code",
        "scope": "com.intuit.quickbooks.accounting",
        "redirect_uri": QBO_REDIRECT_URI,
        "state": state,
    }
    return f"{QBO_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(authorization_code: str, realm_id: str) -> dict:
    """Exchange the authorization code for access and refresh tokens."""
    auth_header = base64.b64encode(
        f"{QBO_CLIENT_ID}:{QBO_CLIENT_SECRET}".encode()
    ).decode()

    response = requests.post(
        QBO_TOKEN_URL,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        data={
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": QBO_REDIRECT_URI,
        },
    )
    response.raise_for_status()
    tokens = response.json()
    tokens["realm_id"] = realm_id
    tokens["obtained_at"] = time.time()
    _save_tokens(tokens)
    return tokens


def refresh_access_token() -> dict:
    """Refresh the access token using the refresh token."""
    tokens = _load_tokens()
    if not tokens or "refresh_token" not in tokens:
        raise ValueError("No refresh token available. Please re-authorize.")

    auth_header = base64.b64encode(
        f"{QBO_CLIENT_ID}:{QBO_CLIENT_SECRET}".encode()
    ).decode()

    response = requests.post(
        QBO_TOKEN_URL,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
    )
    response.raise_for_status()
    new_tokens = response.json()
    new_tokens["realm_id"] = tokens.get("realm_id", "")
    new_tokens["obtained_at"] = time.time()
    _save_tokens(new_tokens)
    return new_tokens


def get_access_token() -> str:
    """Get a valid access token, refreshing if necessary."""
    tokens = _load_tokens()
    if not tokens:
        raise ValueError("No tokens stored. Please authorize first via /qbo/auth")

    # Check if token is expired (access tokens last ~1 hour)
    elapsed = time.time() - tokens.get("obtained_at", 0)
    expires_in = tokens.get("expires_in", 3600)
    if elapsed >= (expires_in - 300):  # Refresh 5 min before expiry
        tokens = refresh_access_token()

    return tokens["access_token"]


def get_realm_id() -> str:
    """Get the stored realm (company) ID."""
    tokens = _load_tokens()
    if not tokens:
        raise ValueError("No tokens stored. Please authorize first via /qbo/auth")
    return tokens.get("realm_id", "")


def is_authenticated() -> bool:
    """Check if we have stored tokens."""
    tokens = _load_tokens()
    return tokens is not None and "access_token" in tokens


def _save_tokens(tokens: dict):
    """Save tokens to file."""
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)


def _load_tokens() -> dict:
    """Load tokens from file."""
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)
