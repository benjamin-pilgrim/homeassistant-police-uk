"""Sensor platform for UK Police integration."""
from __future__ import annotations

import logging
import re
from typing import Any


def _strip_html(text: str | None) -> str:
    """Remove HTML tags and normalise whitespace/newlines from API text."""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UK Police sensors from a config entry."""
    coordinator: UKPoliceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # --- Summary sensors ---
    entities.append(UKPoliceTotalCrimesSensor(coordinator, entry))
    entities.append(UKPoliceCrimeTrendSensor(coordinator, entry))
    entities.append(UKPoliceStopSearchTotalSensor(coordinator, entry))
    entities.append(UKPoliceTeamCountSensor(coordinator, entry))
    entities.append(UKPoliceUpcomingEventsSensor(coordinator, entry))
    entities.append(UKPolicePrioritiesCountSensor(coordinator, entry))
    entities.append(UKPoliceDataLastUpdatedSensor(coordinator, entry))
    entities.append(UKPoliceForceTelephoneSensor(coordinator, entry))
    entities.append(UKPoliceNextEventSensor(coordinator, entry))
    entities.append(UKPoliceTeamNamesSensor(coordinator, entry))
    entities.append(UKPolicePriorityIssuesSensor(coordinator, entry))
    entities.append(UKPoliceOutcomesSensor(coordinator, entry))
    entities.append(UKPoliceStopSearchByObjectSensor(coordinator, entry))
    entities.append(UKPoliceStopSearchByOutcomeSensor(coordinator, entry))
    entities.append(UKPoliceStopSearchByEthnicitySensor(coordinator, entry))
    entities.append(UKPoliceMonthlyTrendSensor(coordinator, entry))

    # --- Per-category crime count sensors ---
    for category_id, category_name in CRIME_CATEGORIES.items():
        if category_id == "all-crime":
            continue  # covered by total crimes sensor
        entities.append(
            UKPoliceCrimeCategorySensor(coordinator, entry, category_id, category_name)
        )

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class UKPoliceBaseSensor(CoordinatorEntity[UKPoliceDataUpdateCoordinator], SensorEntity):
    """Base sensor for UK Police."""

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
            name=f"{self._force_name} – {self._neighbourhood_name}",
            manufacturer="data.police.uk",
            model="UK Police API",
            entry_type="service",
        )

    @property
    def _computed(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get("computed", {})
        return {}


# ---------------------------------------------------------------------------
# Summary sensors
# ---------------------------------------------------------------------------

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
            "by_category": self._computed.get("crime_counts_by_category", {}),
            "month": self.coordinator.client.latest_month(),
        }


class UKPoliceCrimeTrendSensor(UKPoliceBaseSensor):
    """Crime trend: rising / falling / stable."""

    _attr_name = "Crime Trend"
    _attr_icon = "mdi:trending-up"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_crime_trend"

    @property
    def native_value(self) -> str | None:
        return self._computed.get("crime_trend")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "monthly_totals": self._computed.get("monthly_crime_totals", []),
            "months": self.coordinator.data.get("month_strings", []) if self.coordinator.data else [],
        }


class UKPoliceMonthlyTrendSensor(UKPoliceBaseSensor):
    """Numeric crime count for the latest month (for history graphs)."""

    _attr_name = "Monthly Crime Count"
    _attr_icon = "mdi:chart-line"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "crimes"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_monthly_crime_count"

    @property
    def native_value(self) -> int | None:
        totals = self._computed.get("monthly_crime_totals", [])
        return totals[0] if totals else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "all_months": dict(
                zip(
                    self.coordinator.data.get("month_strings", []) if self.coordinator.data else [],
                    self._computed.get("monthly_crime_totals", []),
                )
            )
        }


class UKPoliceCrimeCategorySensor(UKPoliceBaseSensor):
    """Crime count for a specific crime category."""

    _attr_icon = "mdi:police-badge-outline"
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
        self._attr_name = f"Crimes – {category_name}"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_crimes_{self._category_id}"

    @property
    def native_value(self) -> int:
        counts = self._computed.get("crime_counts_by_category", {})
        return counts.get(self._category_id, 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "category": self._category_id,
            "month": self.coordinator.client.latest_month(),
        }


class UKPoliceOutcomesSensor(UKPoliceBaseSensor):
    """Crime outcomes breakdown."""

    _attr_name = "Crime Outcomes"
    _attr_icon = "mdi:gavel"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "outcomes"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_outcomes"

    @property
    def native_value(self) -> int:
        return sum(self._computed.get("outcome_counts", {}).values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"by_outcome": self._computed.get("outcome_counts", {})}


# ---------------------------------------------------------------------------
# Stop & Search sensors
# ---------------------------------------------------------------------------

class UKPoliceStopSearchTotalSensor(UKPoliceBaseSensor):
    """Total stop & searches in the latest month."""

    _attr_name = "Stop & Searches"
    _attr_icon = "mdi:account-search"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "searches"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_stop_search_total"

    @property
    def native_value(self) -> int | None:
        return self._computed.get("total_stop_search")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "by_object_of_search": self._computed.get("stop_search_by_object", {}),
            "by_outcome": self._computed.get("stop_search_by_outcome", {}),
            "month": self.coordinator.client.latest_month(),
        }


class UKPoliceStopSearchByObjectSensor(UKPoliceBaseSensor):
    """Stop & search breakdown by object of search."""

    _attr_name = "Stop & Search – Object of Search"
    _attr_icon = "mdi:magnify-scan"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_stop_search_by_object"

    @property
    def native_value(self) -> str | None:
        by_object = self._computed.get("stop_search_by_object", {})
        if not by_object:
            return "none"
        top = max(by_object, key=by_object.get)
        return top

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"breakdown": self._computed.get("stop_search_by_object", {})}


class UKPoliceStopSearchByOutcomeSensor(UKPoliceBaseSensor):
    """Stop & search breakdown by outcome."""

    _attr_name = "Stop & Search – Outcomes"
    _attr_icon = "mdi:clipboard-check-outline"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_stop_search_by_outcome"

    @property
    def native_value(self) -> str | None:
        by_outcome = self._computed.get("stop_search_by_outcome", {})
        if not by_outcome:
            return "none"
        top = max(by_outcome, key=by_outcome.get)
        return top

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"breakdown": self._computed.get("stop_search_by_outcome", {})}


class UKPoliceStopSearchByEthnicitySensor(UKPoliceBaseSensor):
    """Stop & search breakdown by self-defined ethnicity."""

    _attr_name = "Stop & Search – Ethnicity"
    _attr_icon = "mdi:account-group"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_stop_search_by_ethnicity"

    @property
    def native_value(self) -> int | None:
        return self._computed.get("total_stop_search")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "by_ethnicity": self._computed.get("stop_search_by_ethnicity", {}),
            "by_age_range": self._computed.get("stop_search_by_age", {}),
            "by_gender": self._computed.get("stop_search_by_gender", {}),
        }


# ---------------------------------------------------------------------------
# Neighbourhood team sensors
# ---------------------------------------------------------------------------

class UKPoliceTeamCountSensor(UKPoliceBaseSensor):
    """Number of officers in the neighbourhood team."""

    _attr_name = "Neighbourhood Team Size"
    _attr_icon = "mdi:account-tie-hat"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "officers"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_team_count"

    @property
    def native_value(self) -> int | None:
        return self._computed.get("team_count")


class UKPoliceTeamNamesSensor(UKPoliceBaseSensor):
    """Names of neighbourhood policing team members."""

    _attr_name = "Neighbourhood Team"
    _attr_icon = "mdi:badge-account"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_team_names"

    @property
    def native_value(self) -> str | None:
        names = self._computed.get("team_names", [])
        return names[0] if names else "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"all_officers": self._computed.get("team_names", [])}


# ---------------------------------------------------------------------------
# Events & priorities
# ---------------------------------------------------------------------------

class UKPoliceUpcomingEventsSensor(UKPoliceBaseSensor):
    """Number of upcoming neighbourhood events/meetings."""

    _attr_name = "Upcoming Events"
    _attr_icon = "mdi:calendar-star"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "events"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_upcoming_events"

    @property
    def native_value(self) -> int | None:
        return self._computed.get("upcoming_events_count")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        events = self.coordinator.data.get("neighbourhood_events", []) if self.coordinator.data else []
        return {
            "events": [
                {
                    "title": _strip_html(e.get("title", "")),
                    "description": _strip_html(e.get("description", "")),
                    "date": e.get("start_date", ""),
                    # The API returns address as either a plain string or an object
                    "address": (
                        e["address"]
                        if isinstance(e.get("address"), str)
                        else (e.get("address") or {}).get("address_1", "")
                    ),
                }
                for e in (events or [])
            ]
        }


class UKPoliceNextEventSensor(UKPoliceBaseSensor):
    """Title of the next neighbourhood event."""

    _attr_name = "Next Event"
    _attr_icon = "mdi:calendar-clock"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_next_event"

    @property
    def native_value(self) -> str | None:
        title = self._computed.get("next_event_title", "")
        return title if title else "None scheduled"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"date": self._computed.get("next_event_date", "")}


class UKPolicePrioritiesCountSensor(UKPoliceBaseSensor):
    """Number of active neighbourhood policing priorities."""

    _attr_name = "Policing Priorities"
    _attr_icon = "mdi:alert-circle-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "priorities"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_priorities_count"

    @property
    def native_value(self) -> int | None:
        return self._computed.get("priorities_count")


class UKPolicePriorityIssuesSensor(UKPoliceBaseSensor):
    """List of neighbourhood policing priority issues."""

    _attr_name = "Priority Issues"
    _attr_icon = "mdi:clipboard-list"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_priority_issues"

    @property
    def native_value(self) -> str | None:
        issues = self._computed.get("priority_issues", [])
        return issues[0] if issues else "None"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        priorities = (
            self.coordinator.data.get("neighbourhood_priorities", [])
            if self.coordinator.data
            else []
        )
        return {
            "priorities": [
                {
                    "issue": _strip_html(p.get("issue", "")),
                    "action": _strip_html(p.get("action", "")),
                    "issue_date": p.get("issue-date", ""),
                }
                for p in (priorities or [])
            ]
        }


# ---------------------------------------------------------------------------
# Force metadata sensors
# ---------------------------------------------------------------------------

class UKPoliceDataLastUpdatedSensor(UKPoliceBaseSensor):
    """Date when the crime data was last updated by the API."""

    _attr_name = "Data Last Updated"
    _attr_icon = "mdi:database-clock"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_data_last_updated"

    @property
    def native_value(self) -> str | None:
        return self._computed.get("data_last_updated") or "Unknown"


class UKPoliceForceTelephoneSensor(UKPoliceBaseSensor):
    """Non-emergency telephone number for the force."""

    _attr_name = "Force Telephone"
    _attr_icon = "mdi:phone"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_force_telephone"

    @property
    def native_value(self) -> str | None:
        return self._computed.get("force_telephone") or "101"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "force_url": self._computed.get("force_url", ""),
            "force_description": self._computed.get("force_description", ""),
        }
