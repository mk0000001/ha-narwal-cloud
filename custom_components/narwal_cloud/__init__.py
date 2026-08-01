"""Set up the unofficial Narwal cloud integration."""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NarwalCloudClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_UUID,
    CONF_DEVICE_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PRODUCT_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from .coordinator import NarwalCloudCoordinator

type NarwalCloudConfigEntry = ConfigEntry[NarwalCloudCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: NarwalCloudConfigEntry
) -> bool:
    """Set up Narwal Cloud from one config entry."""
    data: Mapping[str, str] = entry.data

    async def _store_tokens(access_token: str, refresh_token: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: refresh_token,
            },
        )

    client = NarwalCloudClient(
        async_get_clientsession(hass),
        data[CONF_ACCESS_TOKEN],
        data[CONF_REFRESH_TOKEN],
        data.get(CONF_CLIENT_UUID, uuid.uuid4().hex),
        on_token_update=_store_tokens,
        email=data.get(CONF_EMAIL),
        password=data.get(CONF_PASSWORD),
    )
    coordinator = NarwalCloudCoordinator(
        hass, client, data[CONF_DEVICE_ID], data[CONF_PRODUCT_ID]
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(
        entry,
        [
            Platform.VACUUM,
            Platform.BINARY_SENSOR,
            Platform.SELECT,
            Platform.BUTTON,
            Platform.CAMERA,
            Platform.SENSOR,
        ],
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NarwalCloudConfigEntry) -> bool:
    """Unload a Narwal Cloud config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry,
        [
            Platform.VACUUM,
            Platform.BINARY_SENSOR,
            Platform.SELECT,
            Platform.BUTTON,
            Platform.CAMERA,
            Platform.SENSOR,
        ],
    )
