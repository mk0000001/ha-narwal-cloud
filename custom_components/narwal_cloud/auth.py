"""Authentication models kept separate from Narwal device APIs."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass


def token_account_uuid(token: str) -> str | None:
    """Read the non-secret account UUID claim used as MQTT username."""
    try:
        part = token.split(".")[1]
        decoded = base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))
        payload = json.loads(decoded)
        value = payload.get("uuid") if isinstance(payload, dict) else None
    except (IndexError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, str) and len(value) == 32 else None


@dataclass
class NarwalCredentials:
    """Rotating Narwal session credentials."""

    access_token: str
    refresh_token: str
    client_uuid: str

    def __post_init__(self) -> None:
        self.client_uuid = (
            token_account_uuid(self.access_token) or self.client_uuid
        )

    def rotate(self, access_token: str, refresh_token: str) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_uuid = (
            token_account_uuid(access_token) or self.client_uuid
        )

