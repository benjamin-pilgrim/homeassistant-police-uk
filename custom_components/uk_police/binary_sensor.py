"""Binary sensor platform for UK Police integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_FORCE_NAME, CONF_NEIGHBOURHOOD_NAME, DOMAIN
from .coordinator import UKPoliceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UK Police binary sensors."""
    coordinator: UKPoliceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            UKPoliceUpcomingEventsBinarySensor(coordinator, entry),
            UKPoliceHighCrimeAlertBinarySensor(coordinator, entry),
            UKPoliceActivePrioritiesBinarySensor(coordinator, entry),
            UKPoliceRisingCrimeBinarySensor(coordinator, entry),
            UKPoliceTeamActiveBinarySensor(coordinator, entry),
        ]
    )


class UKPoliceBaseBinarySensor(
    CoordinatorEntity[UKPoliceDataUpdateCoordinator], BinarySensorEntity
):
    """Base binary sensor for UK Police."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UKPoliceDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        force_name = self._entry.data.get(CONF_FORCE_NAME, "")
        neighbourhood_name = self._entry.data.get(CONF_NEIGHBOURHOOD_NAME, "")
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"{force_name} – {neighbourhood_name}",
            manufacturer="data.police.uk",
            model="UK Police API",
            entry_type="service",
        )

    @property
    def _computed(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get("computed", {})
        return {}


class UKPoliceUpcomingEventsBinarySensor(UKPoliceBaseBinarySensor):
    """True when there are upcoming neighbourhood events."""

    _attr_name = "Upcoming Events"
    _attr_icon = "mdi:calendar-check"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_has_upcoming_events"

    @property
    def is_on(self) -> bool:
        return bool(self._computed.get("has_upcoming_events", False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "event_count": self._computed.get("upcoming_events_count", 0),
            "next_event": self._computed.get("next_event_title", ""),
            "next_event_date": self._computed.get("next_event_date", ""),
        }


class UKPoliceHighCrimeAlertBinarySensor(UKPoliceBaseBinarySensor):
    """True when crime count in latest month exceeds a threshold (top quartile trigger)."""

    _attr_name = "High Crime Alert"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert"

    # Threshold: flag if 50+ crimes in latest month (street-level radius ~1 mile)
    THRESHOLD = 50

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_high_crime_alert"

    @property
    def is_on(self) -> bool:
        total = self._computed.get("total_crimes", 0) or 0
        return total >= self.THRESHOLD

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "total_crimes": self._computed.get("total_crimes", 0),
            "threshold": self.THRESHOLD,
            "month": self.coordinator.client.latest_month(),
        }


class UKPoliceActivePrioritiesBinarySensor(UKPoliceBaseBinarySensor):
    """True when the neighbourhood has active policing priorities."""

    _attr_name = "Active Policing Priorities"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:shield-alert"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_active_priorities"

    @property
    def is_on(self) -> bool:
        return (self._computed.get("priorities_count", 0) or 0) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "priority_count": self._computed.get("priorities_count", 0),
            "issues": self._computed.get("priority_issues", []),
        }


class UKPoliceRisingCrimeBinarySensor(UKPoliceBaseBinarySensor):
    """True when the crime trend is rising."""

    _attr_name = "Rising Crime Trend"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:trending-up"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_rising_crime"

    @property
    def is_on(self) -> bool:
        return self._computed.get("crime_trend") == "rising"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "trend": self._computed.get("crime_trend", "unknown"),
            "monthly_totals": self._computed.get("monthly_crime_totals", []),
        }


class UKPoliceTeamActiveBinarySensor(UKPoliceBaseBinarySensor):
    """True when there are assigned officers in the neighbourhood team."""

    _attr_name = "Neighbourhood Team Assigned"
    _attr_icon = "mdi:account-tie-hat"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_team_active"

    @property
    def is_on(self) -> bool:
        return (self._computed.get("team_count", 0) or 0) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "officer_count": self._computed.get("team_count", 0),
            "officers": self._computed.get("team_names", []),
        }
