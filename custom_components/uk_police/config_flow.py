"""Config flow for UK Police integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv

from .api import UKPoliceApiClient, UKPoliceApiError
from .const import (
    CONF_CRIME_MONTHS,
    CONF_FORCE,
    CONF_FORCE_NAME,
    CONF_INCLUDE_STOP_SEARCH,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MAP_MODE,
    CONF_NEIGHBOURHOOD,
    CONF_NEIGHBOURHOOD_NAME,
    DEFAULT_CRIME_MONTHS,
    DEFAULT_INCLUDE_STOP_SEARCH,
    DEFAULT_MAP_MODE,
    DOMAIN,
    MAP_MODE_GROUPED,
    MAP_MODE_INDIVIDUAL,
)

_LOGGER = logging.getLogger(__name__)


class UKPoliceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for UK Police."""

    VERSION = 1

    def __init__(self) -> None:
        self._forces: dict[str, str] = {}
        self._neighbourhoods: dict[str, str] = {}
        self._selected_force: str = ""
        self._selected_force_name: str = ""
        self._selected_neighbourhood: str = ""
        self._selected_neighbourhood_name: str = ""
        self._neighbourhood_lat: float | None = None
        self._neighbourhood_lng: float | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1 – Ask user whether to auto-detect location or pick manually."""
        return await self.async_step_select_method(user_input)

    async def async_step_select_method(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let user choose auto-detect (HA location) or manual force selection."""
        if user_input is not None:
            if user_input["method"] == "auto":
                return await self.async_step_auto_detect()
            return await self.async_step_select_force()

        return self.async_show_form(
            step_id="select_method",
            data_schema=vol.Schema(
                {
                    vol.Required("method", default="auto"): vol.In(
                        {"auto": "Auto-detect from Home location", "manual": "Select Force & Neighbourhood manually"}
                    )
                }
            ),
            description_placeholders={
                "info": "Auto-detect uses your Home Assistant home location to find your neighbourhood."
            },
        )

    async def async_step_auto_detect(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Auto-detect neighbourhood from HA home coordinates."""
        errors: dict[str, str] = {}

        ha_lat = self.hass.config.latitude
        ha_lng = self.hass.config.longitude

        if not ha_lat or not ha_lng:
            errors["base"] = "no_home_location"
            return self.async_show_form(
                step_id="auto_detect",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        session = aiohttp_client.async_get_clientsession(self.hass)
        client = UKPoliceApiClient(session)

        try:
            result = await client.locate_neighbourhood(ha_lat, ha_lng)
        except UKPoliceApiError as err:
            _LOGGER.error("Error locating neighbourhood: %s", err)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="auto_detect",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        if result is None:
            errors["base"] = "neighbourhood_not_found"
            return self.async_show_form(
                step_id="auto_detect",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        self._selected_force = result["force"]
        self._selected_neighbourhood = result["neighbourhood"]

        # Fetch names for confirmation — space requests to avoid 429
        try:
            forces = await client.get_forces()
            force_map = {f["id"]: f["name"] for f in forces}
            self._selected_force_name = force_map.get(self._selected_force, self._selected_force)

            await asyncio.sleep(1.0)

            neighbourhoods = await client.get_neighbourhoods(self._selected_force)
            nb_map = {n["id"]: n["name"] for n in neighbourhoods}
            self._selected_neighbourhood_name = nb_map.get(
                self._selected_neighbourhood, self._selected_neighbourhood
            )

            await asyncio.sleep(1.0)

            detail = await client.get_neighbourhood_detail(
                self._selected_force, self._selected_neighbourhood
            )
            if detail and detail.get("centre"):
                self._neighbourhood_lat = float(detail["centre"]["latitude"])
                self._neighbourhood_lng = float(detail["centre"]["longitude"])
            else:
                self._neighbourhood_lat = ha_lat
                self._neighbourhood_lng = ha_lng

        except UKPoliceApiError as err:
            _LOGGER.warning("Could not fetch neighbourhood details: %s", err)
            self._neighbourhood_lat = ha_lat
            self._neighbourhood_lng = ha_lng

        return await self.async_step_confirm()

    async def async_step_select_force(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2 – Select police force."""
        errors: dict[str, str] = {}

        if not self._forces:
            session = aiohttp_client.async_get_clientsession(self.hass)
            client = UKPoliceApiClient(session)
            try:
                forces = await client.get_forces()
                self._forces = {f["id"]: f["name"] for f in forces}
            except UKPoliceApiError as err:
                _LOGGER.error("Error fetching forces: %s", err)
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="select_force",
                    data_schema=vol.Schema({vol.Required(CONF_FORCE): str}),
                    errors=errors,
                )

        if user_input is not None:
            self._selected_force = user_input[CONF_FORCE]
            self._selected_force_name = self._forces.get(self._selected_force, self._selected_force)
            return await self.async_step_select_neighbourhood()

        sorted_forces = dict(sorted(self._forces.items(), key=lambda x: x[1]))

        return self.async_show_form(
            step_id="select_force",
            data_schema=vol.Schema(
                {vol.Required(CONF_FORCE): vol.In(sorted_forces)}
            ),
        )

    async def async_step_select_neighbourhood(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3 – Select neighbourhood within the chosen force."""
        errors: dict[str, str] = {}

        if not self._neighbourhoods:
            session = aiohttp_client.async_get_clientsession(self.hass)
            client = UKPoliceApiClient(session)
            try:
                nbs = await client.get_neighbourhoods(self._selected_force)
                self._neighbourhoods = {n["id"]: n["name"] for n in nbs}
            except UKPoliceApiError as err:
                _LOGGER.error("Error fetching neighbourhoods: %s", err)
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="select_neighbourhood",
                    data_schema=vol.Schema({vol.Required(CONF_NEIGHBOURHOOD): str}),
                    errors=errors,
                )

        if user_input is not None:
            self._selected_neighbourhood = user_input[CONF_NEIGHBOURHOOD]
            self._selected_neighbourhood_name = self._neighbourhoods.get(
                self._selected_neighbourhood, self._selected_neighbourhood
            )

            # Fetch centre coordinates of the neighbourhood
            session = aiohttp_client.async_get_clientsession(self.hass)
            client = UKPoliceApiClient(session)
            try:
                detail = await client.get_neighbourhood_detail(
                    self._selected_force, self._selected_neighbourhood
                )
                if detail and detail.get("centre"):
                    self._neighbourhood_lat = float(detail["centre"]["latitude"])
                    self._neighbourhood_lng = float(detail["centre"]["longitude"])
                else:
                    self._neighbourhood_lat = self.hass.config.latitude
                    self._neighbourhood_lng = self.hass.config.longitude
            except UKPoliceApiError:
                self._neighbourhood_lat = self.hass.config.latitude
                self._neighbourhood_lng = self.hass.config.longitude

            return await self.async_step_confirm()

        sorted_nbs = dict(sorted(self._neighbourhoods.items(), key=lambda x: x[1]))

        return self.async_show_form(
            step_id="select_neighbourhood",
            data_schema=vol.Schema(
                {vol.Required(CONF_NEIGHBOURHOOD): vol.In(sorted_nbs)}
            ),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Final confirmation step with optional settings."""
        if user_input is not None:
            await self.async_set_unique_id(
                f"{self._selected_force}_{self._selected_neighbourhood}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{self._selected_force_name} – {self._selected_neighbourhood_name}",
                data={
                    CONF_FORCE: self._selected_force,
                    CONF_FORCE_NAME: self._selected_force_name,
                    CONF_NEIGHBOURHOOD: self._selected_neighbourhood,
                    CONF_NEIGHBOURHOOD_NAME: self._selected_neighbourhood_name,
                    CONF_LATITUDE: self._neighbourhood_lat,
                    CONF_LONGITUDE: self._neighbourhood_lng,
                },
                options={
                    CONF_INCLUDE_STOP_SEARCH: user_input.get(
                        CONF_INCLUDE_STOP_SEARCH, DEFAULT_INCLUDE_STOP_SEARCH
                    ),
                    CONF_CRIME_MONTHS: user_input.get(CONF_CRIME_MONTHS, DEFAULT_CRIME_MONTHS),
                    CONF_MAP_MODE: user_input.get(CONF_MAP_MODE, DEFAULT_MAP_MODE),
                },
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INCLUDE_STOP_SEARCH, default=DEFAULT_INCLUDE_STOP_SEARCH
                    ): bool,
                    vol.Optional(
                        CONF_CRIME_MONTHS, default=DEFAULT_CRIME_MONTHS
                    ): vol.In({1: "1 month", 3: "3 months", 6: "6 months", 12: "12 months"}),
                    vol.Optional(
                        CONF_MAP_MODE, default=DEFAULT_MAP_MODE
                    ): vol.In({MAP_MODE_GROUPED: "Grouped by category", MAP_MODE_INDIVIDUAL: "Individual incidents"}),
                }
            ),
            description_placeholders={
                "force": self._selected_force_name,
                "neighbourhood": self._selected_neighbourhood_name,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "UKPoliceOptionsFlow":
        """Return options flow handler."""
        return UKPoliceOptionsFlow(config_entry)


class UKPoliceOptionsFlow(config_entries.OptionsFlow):
    """Handle options for UK Police integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INCLUDE_STOP_SEARCH,
                        default=options.get(CONF_INCLUDE_STOP_SEARCH, DEFAULT_INCLUDE_STOP_SEARCH),
                    ): bool,
                    vol.Optional(
                        CONF_CRIME_MONTHS,
                        default=options.get(CONF_CRIME_MONTHS, DEFAULT_CRIME_MONTHS),
                    ): vol.In({1: "1 month", 3: "3 months", 6: "6 months", 12: "12 months"}),
                    vol.Optional(
                        CONF_MAP_MODE,
                        default=options.get(CONF_MAP_MODE, DEFAULT_MAP_MODE),
                    ): vol.In({MAP_MODE_GROUPED: "Grouped by category", MAP_MODE_INDIVIDUAL: "Individual incidents"}),
                }
            ),
        )
