"""Focused tests for account authentication without Home Assistant imports."""

from __future__ import annotations

import asyncio
import base64
import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).parents[1] / "custom_components" / "narwal_cloud"


def _load_modules():
    aiohttp = types.ModuleType("aiohttp")
    aiohttp.ClientError = type("ClientError", (Exception,), {})
    aiohttp.ClientSession = object
    sys.modules.setdefault("aiohttp", aiohttp)
    package = types.ModuleType("narwal_cloud")
    package.__path__ = [str(ROOT)]
    sys.modules["narwal_cloud"] = package
    for name in ("auth", "mqtt", "protocol", "const", "api"):
        spec = importlib.util.spec_from_file_location(
            f"narwal_cloud.{name}", ROOT / f"{name}.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return sys.modules["narwal_cloud.auth"], sys.modules["narwal_cloud.api"]


AUTH, API = _load_modules()


class _Response:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def json(self, **_kwargs):
        return {"result": {"token": "access", "refreshToken": "refresh"}}


class _Session:
    body = None
    headers = None

    def post(self, *_args, **kwargs):
        self.body = kwargs["json"]
        self.headers = kwargs["headers"]
        return _Response()


def test_password_encryption_and_token_parser() -> None:
    first = AUTH.encrypt_account_password("test-password")
    second = AUTH.encrypt_account_password("test-password")
    assert len(base64.b64decode(first)) == 128
    assert first != second
    assert AUTH.token_pair_from_payload(
        {"result": {"token": "access", "refreshToken": "refresh"}}
    ) == ("access", "refresh")


def test_account_login_never_sends_plaintext_password() -> None:
    async def run() -> None:
        session = _Session()
        stored = []

        async def save(access_token, refresh_token):
            stored.append((access_token, refresh_token))

        client = API.NarwalCloudClient(session, "", "", "client", save)
        await client.async_login_with_email("user@example.com", "plain-secret")
        assert client.access_token == "access"
        assert stored == [("access", "refresh")]
        assert session.body["password"] != "plain-secret"
        assert session.body["encrypted_password"] != "plain-secret"
        assert "authorization" not in session.headers
        assert "auth-token" not in session.headers

    asyncio.run(run())


if __name__ == "__main__":
    test_password_encryption_and_token_parser()
    test_account_login_never_sends_plaintext_password()
    print("authentication tests passed")
