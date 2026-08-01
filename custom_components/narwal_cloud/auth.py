"""Authentication models kept separate from Narwal device APIs."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_der_public_key


# Production public key bundled with Narwal Freo 2.7.03. This encrypts the
# password in transit before the already encrypted HTTPS request is sent. It
# is a public key and contains no account-specific material.
NARWAL_LOGIN_PUBLIC_KEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQD4DMOh3L+BfGpLM4lm1ihHka9y"
    "GtX0AYvabNoi+hOjCQsoFe0hesU05MV2tgqrxfShwOwHEuXd0YLrGPqpe0LYsDD2J"
    "exiQAuNyKIah4kKINVmJkyf0aYPuCueRHIWkWRpsHSozkMDwjFcabMFEaMba7L9J"
    "kmMni8a7hqgcuvyIQIDAQAB"
)


def encrypt_account_password(password: str) -> str:
    """Encrypt a Narwal password using the official app public key."""
    public_key = load_der_public_key(base64.b64decode(NARWAL_LOGIN_PUBLIC_KEY))
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise ValueError("Narwal login key is not an RSA public key")
    encrypted = public_key.encrypt(password.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("ascii")


def token_pair_from_payload(payload: dict) -> tuple[str, str] | None:
    """Find the rotating token pair in known Narwal login responses."""
    candidates = [payload.get("result"), payload]
    result = payload.get("result")
    if isinstance(result, dict):
        candidates.extend(
            [result.get("userInfo"), result.get("authInfo"), result.get("data")]
        )
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        access_token = candidate.get("token") or candidate.get("accessToken")
        refresh_token = candidate.get("refreshToken") or candidate.get(
            "refresh_token"
        )
        if isinstance(access_token, str) and isinstance(refresh_token, str):
            return access_token, refresh_token
    return None


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

