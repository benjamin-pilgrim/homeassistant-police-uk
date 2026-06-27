"""Sensor platform for Police.uk Local Crime."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_FORCE_NAME,
    CONF_NEIGHBOURHOOD_NAME,
    CRIME_CATEGORIES,
    DOMAIN,
)
from .coordinator import UKPoliceDataUpdateCoordinator

_DEFAULT_CATEGORY_ICON = "mdi:police-badge-outline"
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
    "violent-crime": "mdi:knife",
    "other-crime": _DEFAULT_CATEGORY_ICON,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Police.uk Local Crime sensors from a config entry."""
    coordinator: UKPoliceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        UKPoliceDataMonthSensor(coordinator, entry),
        UKPoliceTotalCrimesSensor(coordinator, entry),
    ]

    for category_id, category_name in CRIME_CATEGORIES.items():
        if category_id == "all-crime":
            continue
        entities.append(
            UKPoliceCrimeCategorySensor(coordinator, entry, category_id, category_name)
        )

    async_add_entities(entities)


class UKPoliceBaseSensor(CoordinatorEntity[UKPoliceDataUpdateCoordinator], SensorEntity):
    """Base sensor for Police.uk Local Crime."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UKPoliceDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._force_name = entry.data.get(CONF_FORCE_NAME, "")
        self._neighbourhood_name = entry.data.get(CONF_NEIGHBOURHOOD_NAME, "")

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"{self._force_name} - {self._neighbourhood_name}",
            manufacturer="data.police.uk",
            model="Police.uk Local Crime",
            entry_type="service",
        )

    @property
    def _computed(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get("computed", {})
        return {}

    @property
    def _query_area(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get("query_area", {})
        return {}


class UKPoliceDataMonthSensor(UKPoliceBaseSensor):
    """Latest Police.uk data month."""

    _attr_name = "Data Month"
    _attr_icon = "mdi:calendar-month"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_data_month"

    @property
    def native_value(self) -> str | None:
        return self._computed.get("data_month")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "data_month_fallback": self._computed.get("data_month_fallback", False),
            "query_area": self._query_area,
        }


class UKPoliceTotalCrimesSensor(UKPoliceBaseSensor):
    """Total crimes in the latest available month."""

    _attr_name = "Total Crimes"
    _attr_icon = "mdi:police-badge"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "crimes"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_total_crimes"

    @property
    def native_value(self) -> int | None:
        return self._computed.get("total_crimes")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "month": self._computed.get("data_month", ""),
            "by_category": self._computed.get("crime_counts_by_category", {}),
            "monthly_counts": self._computed.get("monthly_counts", {}),
            "latest_incidents": self._computed.get("latest_incidents", []),
            "incident_count": self._computed.get("latest_incident_count", 0),
            "incidents_truncated": self._computed.get(
                "latest_incidents_truncated", False
            ),
            "query_area": self._query_area,
        }


class UKPoliceCrimeCategorySensor(UKPoliceBaseSensor):
    """Crime count for a specific Police.uk category."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "crimes"

    def __init__(
        self,
        coordinator: UKPoliceDataUpdateCoordinator,
        entry: ConfigEntry,
        category_id: str,
        category_name: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._category_id = category_id
        self._category_name = category_name
        self._attr_name = f"Crimes - {category_name}"
        self._attr_icon = _CATEGORY_ICONS.get(category_id, _DEFAULT_CATEGORY_ICON)

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_crimes_{self._category_id}"

    @property
    def native_value(self) -> int:
        counts = self._computed.get("crime_counts_by_category", {})
        return counts.get(self._category_id, 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        monthly_counts = self._computed.get("category_monthly_counts", {})
        incidents = self._computed.get("category_incidents", {})
        incident_counts = self._computed.get("category_incident_counts", {})
        truncated = self._computed.get("category_incidents_truncated", {})
        approximate_counts = self._computed.get("category_approximate_counts", {})

        return {
            "category": self._category_id,
            "category_name": self._category_name,
            "month": self._computed.get("data_month", ""),
            "monthly_counts": monthly_counts.get(self._category_id, {}),
            "incidents": incidents.get(self._category_id, []),
            "incident_count": incident_counts.get(self._category_id, 0),
            "incidents_truncated": truncated.get(self._category_id, False),
            "by_approximate_location": approximate_counts.get(self._category_id, {}),
            "query_area": self._query_area,
        }
