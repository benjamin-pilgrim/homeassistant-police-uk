"""Config flow for Police.uk Local Crime."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .api import UKPoliceApiClient, UKPoliceApiError
from .const import (
    AREA_MODE_DEFAULT,
    AREA_MODE_RADIUS,
    CONF_AREA_MODE,
    CONF_FORCE,
    CONF_FORCE_NAME,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MAP_MODE,
    CONF_NEIGHBOURHOOD,
    CONF_NEIGHBOURHOOD_NAME,
    CONF_RADIUS_METERS,
    CONF_SETUP_METHOD,
    DEFAULT_AREA_MODE,
    DEFAULT_MAP_MODE,
    DEFAULT_RADIUS_METERS,
    DOMAIN,
    MAP_MODE_GROUPED,
    MAP_MODE_INDIVIDUAL,
    MAP_MODE_NONE,
    MAX_RADIUS_METERS,
    MIN_RADIUS_METERS,
    SETUP_METHOD_AUTO,
    SETUP_METHOD_MANUAL,
)

_LOGGER = logging.getLogger(__name__)

_MAP_MODE_OPTIONS = {
    MAP_MODE_GROUPED: "Grouped by category",
    MAP_MODE_INDIVIDUAL: "Individual incidents",
    MAP_MODE_NONE: "None",
}


class UKPoliceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Police.uk Local Crime."""

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
        self._setup_method: str = SETUP_METHOD_AUTO

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: ask user whether to auto-detect location or pick manually."""
        return await self.async_step_select_method(user_input)

    async def async_step_select_method(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let user choose auto-detect (HA location) or manual force selection."""
        if user_input is not None:
            if user_input["method"] == "auto":
                self._setup_method = SETUP_METHOD_AUTO
                return await self.async_step_auto_detect()
            self._setup_method = SETUP_METHOD_MANUAL
            return await self.async_step_select_force()

        return self.async_show_form(
            step_id="select_method",
            data_schema=vol.Schema(
                {
                    vol.Required("method", default="auto"): vol.In(
                        {"auto": "Auto-detect from Home location", "manual": "Select force and neighbourhood manually"}
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

        if ha_lat is None or ha_lng is None:
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
        self._selected_force_name = self._selected_force
        self._selected_neighbourhood_name = self._selected_neighbourhood

        # Fetch names for confirmation; space requests to avoid 429.
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
        """Step 2: select police force."""
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
        """Step 3: select neighbourhood within the chosen force."""
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
                title=f"{self._selected_force_name} - {self._selected_neighbourhood_name}",
                data={
                    CONF_FORCE: self._selected_force,
                    CONF_FORCE_NAME: self._selected_force_name,
                    CONF_NEIGHBOURHOOD: self._selected_neighbourhood,
                    CONF_NEIGHBOURHOOD_NAME: self._selected_neighbourhood_name,
                    CONF_LATITUDE: self._neighbourhood_lat,
                    CONF_LONGITUDE: self._neighbourhood_lng,
                    CONF_SETUP_METHOD: self._setup_method,
                },
                options=self._entry_options(user_input),
            )

        schema: dict[Any, Any] = {
            vol.Optional(
                CONF_MAP_MODE, default=DEFAULT_MAP_MODE
            ): vol.In(_MAP_MODE_OPTIONS),
        }
        if self._setup_method == SETUP_METHOD_AUTO:
            schema.update(_area_options_schema({}))

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "force": self._selected_force_name,
                "neighbourhood": self._selected_neighbourhood_name,
            },
        )

    def _entry_options(self, user_input: dict[str, Any]) -> dict[str, Any]:
        options = {
            CONF_MAP_MODE: _normalize_map_mode(
                user_input.get(CONF_MAP_MODE, DEFAULT_MAP_MODE)
            ),
        }
        if self._setup_method == SETUP_METHOD_AUTO:
            options[CONF_AREA_MODE] = user_input.get(CONF_AREA_MODE, DEFAULT_AREA_MODE)
            options[CONF_RADIUS_METERS] = user_input.get(
                CONF_RADIUS_METERS, DEFAULT_RADIUS_METERS
            )
        return options

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "UKPoliceOptionsFlow":
        """Return options flow handler."""
        return UKPoliceOptionsFlow(config_entry)


class UKPoliceOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Police.uk Local Crime."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            new_options = dict(user_input)
            new_options[CONF_MAP_MODE] = _normalize_map_mode(
                new_options.get(CONF_MAP_MODE, DEFAULT_MAP_MODE)
            )
            return self.async_create_entry(title="", data=new_options)

        options = self._config_entry.options
        schema: dict[Any, Any] = {
            vol.Optional(
                CONF_MAP_MODE,
                default=options.get(CONF_MAP_MODE, DEFAULT_MAP_MODE),
            ): vol.In(_MAP_MODE_OPTIONS),
        }
        if self._config_entry.data.get(CONF_SETUP_METHOD) == SETUP_METHOD_AUTO:
            schema.update(_area_options_schema(options))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )


def _area_options_schema(options: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Optional(
            CONF_AREA_MODE,
            default=options.get(CONF_AREA_MODE, DEFAULT_AREA_MODE),
        ): vol.In(
            {
                AREA_MODE_DEFAULT: "Default Police.uk area",
                AREA_MODE_RADIUS: "Radius around Home Assistant home location",
            }
        ),
        vol.Optional(
            CONF_RADIUS_METERS,
            default=options.get(CONF_RADIUS_METERS, DEFAULT_RADIUS_METERS),
        ): vol.All(
            vol.Coerce(int),
            vol.Range(min=MIN_RADIUS_METERS, max=MAX_RADIUS_METERS),
        ),
    }


def _normalize_map_mode(value: Any) -> str:
    if value in _MAP_MODE_OPTIONS:
        return str(value)
    return DEFAULT_MAP_MODE
