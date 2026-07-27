"""Config flow for Narwal Cloud."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api import NarwalCloudClient, NarwalCloudError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_UUID,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PRODUCT_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)


class NarwalCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a Narwal account bootstrap token pair."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Validate token pair and discover the first bound robot."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client_uuid = ""
            client = NarwalCloudClient(
                async_get_clientsession(self.hass),
                user_input[CONF_ACCESS_TOKEN],
                user_input[CONF_REFRESH_TOKEN],
                client_uuid,
            )
            try:
                devices = await client.async_get_devices()
            except NarwalCloudError:
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    device = devices[0]
                    device_id = device.get("deviceId")
                    product_id = device.get("productId")
                    if not isinstance(device_id, str) or not isinstance(product_id, str):
                        errors["base"] = "invalid_response"
                    else:
                        await self.async_set_unique_id(device_id)
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=str(device.get("robotName") or "Narwal"),
                            data={
                                **user_input,
                                CONF_ACCESS_TOKEN: client.access_token,
                                CONF_REFRESH_TOKEN: client.refresh_token,
                                CONF_CLIENT_UUID: client.client_uuid,
                                CONF_DEVICE_ID: device_id,
                                CONF_PRODUCT_ID: product_id,
                                CONF_DEVICE_NAME: str(device.get("robotName") or "Narwal"),
                            },
                        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Required(CONF_REFRESH_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "token_guide_url": (
                    "https://github.com/rudyll/narwal_r/blob/main/"
                    "docs/token_setup.md"
                )
            },
        )
