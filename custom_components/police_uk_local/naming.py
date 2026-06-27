"""Name helpers for Police.uk Local Crime."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import (
    AREA_MODE_RADIUS,
    CONF_AREA_MODE,
    CONF_FORCE_NAME,
    CONF_NEIGHBOURHOOD_NAME,
    CONF_RADIUS_METERS,
    CONF_SETUP_METHOD,
    DEFAULT_AREA_MODE,
    DEFAULT_RADIUS_METERS,
    MAX_RADIUS_METERS,
    MIN_RADIUS_METERS,
    SETUP_METHOD_AUTO,
)


def area_name_from_entry(entry: ConfigEntry) -> str:
    """Return the display name for a configured Police.uk area."""
    return area_name_from_values(
        entry.data.get(CONF_FORCE_NAME, ""),
        entry.data.get(CONF_NEIGHBOURHOOD_NAME, ""),
        entry.data.get(CONF_SETUP_METHOD, ""),
        entry.options,
    )


def area_name_from_values(
    force_name: str,
    neighbourhood_name: str,
    setup_method: str,
    options: dict[str, Any],
) -> str:
    """Return the display name for a Police.uk area from raw config values."""
    base_name = _base_area_name(force_name, neighbourhood_name)
    if (
        setup_method == SETUP_METHOD_AUTO
        and options.get(CONF_AREA_MODE, DEFAULT_AREA_MODE) == AREA_MODE_RADIUS
    ):
        return f"{base_name} {_radius_meters(options)}m"
    return base_name


def _base_area_name(force_name: str, neighbourhood_name: str) -> str:
    parts = [part for part in (force_name, neighbourhood_name) if part]
    if parts:
        return " - ".join(parts)
    return "Police.uk Local Crime"


def _radius_meters(options: dict[str, Any]) -> int:
    try:
        radius = int(options.get(CONF_RADIUS_METERS, DEFAULT_RADIUS_METERS))
    except (TypeError, ValueError):
        return DEFAULT_RADIUS_METERS

    if MIN_RADIUS_METERS <= radius <= MAX_RADIUS_METERS:
        return radius
    return DEFAULT_RADIUS_METERS
