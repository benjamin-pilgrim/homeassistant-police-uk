"""UK Police integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .api import UKPoliceApiClient
from .const import DOMAIN
from .coordinator import UKPoliceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.GEO_LOCATION]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UK Police from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = UKPoliceApiClient(session)

    coordinator = UKPoliceDataUpdateCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register services
    _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Remove services when last entry is removed
        if not hass.data[DOMAIN]:
            _unregister_services(hass)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update – reload entry so new options take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    """Register custom services for UK Police."""

    if hass.services.has_service(DOMAIN, "refresh"):
        return

    async def _handle_refresh(call: ServiceCall) -> None:
        """Force-refresh all coordinators or a specific entry."""
        entry_id = call.data.get("entry_id")
        for eid, coordinator in hass.data.get(DOMAIN, {}).items():
            if entry_id is None or eid == entry_id:
                await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        "refresh",
        _handle_refresh,
        schema=vol.Schema(
            {vol.Optional("entry_id"): cv.string}
        ),
    )

    async def _handle_get_crimes(call: ServiceCall) -> None:
        """Fire an event with street-level crimes for chosen entry."""
        entry_id = call.data.get("entry_id")
        for eid, coordinator in hass.data.get(DOMAIN, {}).items():
            if entry_id is None or eid == entry_id:
                crimes = (coordinator.data or {}).get("crimes_street", [])
                hass.bus.async_fire(
                    f"{DOMAIN}_crimes_data",
                    {
                        "entry_id": eid,
                        "crimes": crimes[:200],  # cap payload size
                        "month": coordinator.client.latest_month(),
                    },
                )

    hass.services.async_register(
        DOMAIN,
        "get_crimes",
        _handle_get_crimes,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
    )

    async def _handle_get_stop_search(call: ServiceCall) -> None:
        """Fire an event with stop & search data for chosen entry."""
        entry_id = call.data.get("entry_id")
        for eid, coordinator in hass.data.get(DOMAIN, {}).items():
            if entry_id is None or eid == entry_id:
                ss = (coordinator.data or {}).get("stop_search", [])
                hass.bus.async_fire(
                    f"{DOMAIN}_stop_search_data",
                    {
                        "entry_id": eid,
                        "stop_searches": ss[:200],
                        "month": coordinator.client.latest_month(),
                    },
                )

    hass.services.async_register(
        DOMAIN,
        "get_stop_search",
        _handle_get_stop_search,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
    )


def _unregister_services(hass: HomeAssistant) -> None:
    hass.services.async_remove(DOMAIN, "refresh")
    hass.services.async_remove(DOMAIN, "get_crimes")
    hass.services.async_remove(DOMAIN, "get_stop_search")
