"""Constants for the unofficial Narwal cloud integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "narwal_cloud"
NAME = "Narwal"

API_BASE_URL = "https://kr-app.narwaltech.com"
CLIENT_APPLICATION_ID = "2E3t5It3Dr"
CLIENT_APP_VERSION = "2.7.03"
CLIENT_VERSION_CODE = "175"

CONF_ACCESS_TOKEN = "access_token"
CONF_AUTH_METHOD = "auth_method"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_DEVICE_ID = "device_id"
CONF_PRODUCT_ID = "product_id"
CONF_DEVICE_NAME = "device_name"
CONF_CLIENT_UUID = "client_uuid"

AUTH_METHOD_ACCOUNT = "account"
AUTH_METHOD_TOKEN = "token"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
