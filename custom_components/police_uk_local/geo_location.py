"""Geo location platform for Police.uk Local Crime map pins."""
from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from math import atan2, cos, radians, sin, sqrt
from typing import Any

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_FORCE_NAME,
    CONF_MAP_MODE,
    CONF_NEIGHBOURHOOD_NAME,
    CRIME_CATEGORIES,
    DEFAULT_MAP_MODE,
    DOMAIN,
    MAP_MODE_INDIVIDUAL,
)
from .coordinator import UKPoliceDataUpdateCoordinator, normalize_incident

_LOGGER = logging.getLogger(__name__)

# Category to MDI icon
_CATEGORY_ICONS: dict[str, str] = {
    "anti-social-behaviour": "mdi:account-alert",
    "bicycle-theft": "mdi:bicycle",
    "burglary": "mdi:home-alert",
    "criminal-damage-arson": "mdi:fire-alert",
    "drugs": "mdi:pill",
    "other-theft": "mdi:bag-personal-off",
    "possession-of-weapons": "mdi:knife",
    "public-order": "mdi:account-group",
    "robbery": "mdi:robber",
    "shoplifting": "mdi:storefront-outline",
    "theft-from-the-person": "mdi:hand-coin",
    "vehicle-crime": "mdi:car",
    "violent-crime": "mdi:account-injury",
    "other-crime": "mdi:police-badge-outline",
    "all-crime": "mdi:map-marker-alert",
}


def _haversine_mi(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the great-circle distance in miles between two lat/lng points."""
    R = 3_958.8  # Earth radius in miles
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lam = radians(lng2 - lng1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lam / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _centroid(crimes: list[dict]) -> tuple[float | None, float | None]:
    """Return the mean lat/lng of a list of crime records."""
    lats, lngs = [], []
    for c in crimes:
        loc = c.get("location") or {}
        try:
            lats.append(float(loc["latitude"]))
            lngs.append(float(loc["longitude"]))
        except (KeyError, TypeError, ValueError):
            pass
    if not lats:
        return None, None
    return sum(lats) / len(lats), sum(lngs) / len(lngs)


def _crime_key(crime: dict) -> str:
    """Return a stable unique key for an individual crime record.

    Uses persistent_id first, then the API id, then a hash of stable fields.
    """
    pid = crime.get("persistent_id", "")
    if pid:
        return str(pid)
    api_id = crime.get("id")
    if api_id:
        return str(api_id)

    fallback = json.dumps(crime, sort_keys=True, default=str)
    return hashlib.sha1(fallback.encode("utf-8")).hexdigest()


def _remove_from_registry(hass: HomeAssistant, pin: "_UKPolicePinBase") -> None:
    """Remove a pin from the entity registry (and therefore the state machine)."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("geo_location", DOMAIN, pin.unique_id)
    if entity_id:
        registry.async_remove(entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up geo_location entities based on the configured map mode."""
    coordinator: UKPoliceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    map_mode = entry.options.get(CONF_MAP_MODE, DEFAULT_MAP_MODE)
    home_lat: float = coordinator.lat
    home_lng: float = coordinator.lng

    # Purge entity registry entries that belong to the OTHER map mode.
    # This handles the case where the user switches mode in options; without this,
    # the old entities stay in the registry and show as "Unavailable" forever.
    registry = er.async_get(hass)
    stale_prefix = (
        f"{entry.entry_id}_crime_"
        if map_mode != MAP_MODE_INDIVIDUAL
        else f"{entry.entry_id}_category_"
    )
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity_entry.unique_id.startswith(stale_prefix):
            registry.async_remove(entity_entry.entity_id)

    if map_mode == MAP_MODE_INDIVIDUAL:
        _setup_individual(hass, entry, coordinator, async_add_entities, home_lat, home_lng)
    else:
        _setup_grouped(hass, entry, coordinator, async_add_entities, home_lat, home_lng)


def _setup_grouped(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: UKPoliceDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    home_lat: float,
    home_lng: float,
) -> None:
    """Register listener for grouped-by-category map pins."""
    tracked: dict[str, UKPoliceCategoryPin] = {}

    @callback
    def _handle_update() -> None:
        crimes = (coordinator.data or {}).get("crimes_street", []) or []

        by_category: dict[str, list[dict]] = defaultdict(list)
        for crime in crimes:
            cat = crime.get("category", "other-crime")
            by_category[cat].append(crime)

        new_entities: list[UKPoliceCategoryPin] = []
        seen: set[str] = set()

        for category, cat_crimes in by_category.items():
            seen.add(category)
            if category not in tracked:
                pin = UKPoliceCategoryPin(
                    coordinator, entry, category, cat_crimes, home_lat, home_lng
                )
                tracked[category] = pin
                new_entities.append(pin)
            else:
                # Guard: only update state if entity has been added to HA already.
                # Without this, a double-call during setup causes a crash because
                # hass is still None on entities queued but not yet registered.
                if tracked[category].hass is not None:
                    tracked[category].update_crimes(cat_crimes, home_lat, home_lng)

        for stale_cat in [c for c in list(tracked) if c not in seen]:
            _remove_from_registry(hass, tracked[stale_cat])
            del tracked[stale_cat]

        if new_entities:
            async_add_entities(new_entities)

    cancel_listener = coordinator.async_add_listener(_handle_update)
    entry.async_on_unload(cancel_listener)
    # Explicit initial call ensures entities are created even in HA versions where
    # async_add_listener does not fire the callback immediately on registration.
    # The hass-guard above prevents any crash if it was already called by the listener.
    _handle_update()


def _setup_individual(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: UKPoliceDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    home_lat: float,
    home_lng: float,
) -> None:
    """Register listener for individual crime incident map pins."""
    tracked: dict[str, UKPoliceCrimePin] = {}

    @callback
    def _handle_update() -> None:
        crimes = (coordinator.data or {}).get("crimes_street", []) or []

        new_entities: list[UKPoliceCrimePin] = []
        seen: set[str] = set()
        for crime in crimes:
            key = _crime_key(crime)
            seen.add(key)
            if key not in tracked:
                pin = UKPoliceCrimePin(coordinator, entry, key, crime, home_lat, home_lng)
                tracked[key] = pin
                new_entities.append(pin)
            else:
                # Guard: only update state if entity has been added to HA already.
                if tracked[key].hass is not None:
                    tracked[key].update_crime(crime, home_lat, home_lng)

        for stale_key in [k for k in list(tracked) if k not in seen]:
            _remove_from_registry(hass, tracked[stale_key])
            del tracked[stale_key]

        if new_entities:
            async_add_entities(new_entities)

    cancel_listener = coordinator.async_add_listener(_handle_update)
    entry.async_on_unload(cancel_listener)
    # Explicit initial call ensures entities are created even in HA versions where
    # async_add_listener does not fire the callback immediately on registration.
    # The hass-guard above prevents any crash if it was already called by the listener.
    _handle_update()


# ---------------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------------

class _UKPolicePinBase(
    CoordinatorEntity[UKPoliceDataUpdateCoordinator], GeolocationEvent
):
    """Shared base for all Police.uk Local Crime geo_location pins."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_unit_of_measurement = "mi"

    def __init__(
        self,
        coordinator: UKPoliceDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        GeolocationEvent.__init__(self)
        self._entry = entry
        # Per-entry source so map cards can filter by location.
        # Hyphens in API IDs (e.g. "city-of-london", "west-end") are normalised to
        # underscores so the value is safe to paste directly into a Lovelace card.
        # Results in e.g. "police_uk_local_metropolitan_west_end".
        self._attr_source = (
            f"{DOMAIN}_{coordinator.force_id}_{coordinator.neighbourhood_id}"
        ).replace("-", "_")

    @property
    def device_info(self) -> DeviceInfo:
        force_name = self._entry.data.get(CONF_FORCE_NAME, "")
        neighbourhood_name = self._entry.data.get(CONF_NEIGHBOURHOOD_NAME, "")
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"{force_name} - {neighbourhood_name}",
            manufacturer="data.police.uk",
            model="Police.uk Local Crime",
            entry_type="service",
        )


# ---------------------------------------------------------------------------
# Grouped mode entity
# ---------------------------------------------------------------------------

class UKPoliceCategoryPin(_UKPolicePinBase):
    """One map pin per crime category, centred on the mean position of all crimes in that category."""

    def __init__(
        self,
        coordinator: UKPoliceDataUpdateCoordinator,
        entry: ConfigEntry,
        category: str,
        crimes: list[dict],
        home_lat: float,
        home_lng: float,
    ) -> None:
        super().__init__(coordinator, entry)
        self._category = category
        self._crimes = crimes
        self._refresh_derived(home_lat, home_lng)

    def _refresh_derived(self, home_lat: float, home_lng: float) -> None:
        label = CRIME_CATEGORIES.get(
            self._category, self._category.replace("-", " ").title()
        )
        count = len(self._crimes)
        self._attr_name = f"{label} ({count})"
        self._attr_icon = _CATEGORY_ICONS.get(self._category, "mdi:map-marker-alert")
        lat, lng = _centroid(self._crimes)
        self._attr_latitude = lat
        self._attr_longitude = lng
        if lat is not None and lng is not None:
            self._attr_distance = round(_haversine_mi(home_lat, home_lng, lat, lng), 2)
        else:
            self._attr_distance = 0.0

    @callback
    def update_crimes(self, crimes: list[dict], home_lat: float, home_lng: float) -> None:
        """Refresh crimes list and recalculate derived attributes."""
        self._crimes = crimes
        self._refresh_derived(home_lat, home_lng)
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_category_{self._category}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        month = data.get("data_month", "")
        incidents = [normalize_incident(crime) for crime in self._crimes]
        return {
            "category": self._category,
            "count": len(self._crimes),
            "month": month,
            "incidents": incidents,
            "query_area": data.get("query_area", {}),
        }


# ---------------------------------------------------------------------------
# Individual mode entity
# ---------------------------------------------------------------------------

class UKPoliceCrimePin(_UKPolicePinBase):
    """One map pin per individual crime incident."""

    def __init__(
        self,
        coordinator: UKPoliceDataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
        crime: dict,
        home_lat: float,
        home_lng: float,
    ) -> None:
        super().__init__(coordinator, entry)
        self._key = key
        self._crime = crime
        self._refresh_derived(home_lat, home_lng)

    def _refresh_derived(self, home_lat: float, home_lng: float) -> None:
        category = self._crime.get("category", "other-crime")
        label = CRIME_CATEGORIES.get(category, category.replace("-", " ").title())
        loc = self._crime.get("location") or {}
        street = (loc.get("street") or {}).get("name", "Unknown street")
        self._attr_name = f"{label} - {street}"
        self._attr_icon = _CATEGORY_ICONS.get(category, "mdi:map-marker-alert")
        try:
            lat = float(loc["latitude"])
            lng = float(loc["longitude"])
            self._attr_latitude = lat
            self._attr_longitude = lng
            self._attr_distance = round(_haversine_mi(home_lat, home_lng, lat, lng), 2)
        except (KeyError, TypeError, ValueError):
            self._attr_latitude = None
            self._attr_longitude = None
            self._attr_distance = 0.0

    @callback
    def update_crime(self, crime: dict, home_lat: float, home_lng: float) -> None:
        """Refresh crime data and recalculate derived attributes."""
        self._crime = crime
        self._refresh_derived(home_lat, home_lng)
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_crime_{self._key}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        incident = normalize_incident(self._crime)
        return {
            **incident,
            "query_area": data.get("query_area", {}),
        }
