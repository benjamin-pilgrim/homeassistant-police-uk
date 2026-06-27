"""DataUpdateCoordinator for Police.uk Local Crime."""
from __future__ import annotations

import asyncio
import logging
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import UKPoliceApiClient, UKPoliceApiError
from .const import (
    AREA_MODE_DEFAULT,
    AREA_MODE_RADIUS,
    CONF_AREA_MODE,
    CONF_CRIME_MONTHS,
    CONF_FORCE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NEIGHBOURHOOD,
    CONF_RADIUS_METERS,
    CONF_SETUP_METHOD,
    CRIME_CATEGORIES,
    DEFAULT_AREA_MODE,
    DEFAULT_CRIME_MONTHS,
    DEFAULT_RADIUS_METERS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_RADIUS_METERS,
    MIN_RADIUS_METERS,
    POLYGON_POINTS,
    SETUP_METHOD_AUTO,
)
from .geometry import circle_polygon

_LOGGER = logging.getLogger(__name__)

_INTER_REQUEST_DELAY = 2.0
_CATEGORY_INCIDENT_CAP = 50
_TOTAL_INCIDENT_CAP = 100


class UKPoliceDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetch and cache crime data for one configured Police.uk area."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: UKPoliceApiClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.entry = entry

        self.force_id: str = entry.data[CONF_FORCE]
        self.neighbourhood_id: str = entry.data[CONF_NEIGHBOURHOOD]
        self.lat: float = entry.data[CONF_LATITUDE]
        self.lng: float = entry.data[CONF_LONGITUDE]

        self._last_data_date: str | None = None
        self._last_query_signature: tuple[Any, ...] | None = None

    @property
    def crime_months(self) -> int:
        return self.entry.options.get(CONF_CRIME_MONTHS, DEFAULT_CRIME_MONTHS)

    @property
    def area_mode(self) -> str:
        """Return the active area mode, limiting radius mode to auto entries."""
        if self.entry.data.get(CONF_SETUP_METHOD) != SETUP_METHOD_AUTO:
            return AREA_MODE_DEFAULT

        mode = self.entry.options.get(CONF_AREA_MODE, DEFAULT_AREA_MODE)
        if mode == AREA_MODE_RADIUS:
            return AREA_MODE_RADIUS
        return AREA_MODE_DEFAULT

    @property
    def radius_meters(self) -> int:
        """Return a validated radius, falling back to the MVP default."""
        try:
            radius = int(self.entry.options.get(CONF_RADIUS_METERS, DEFAULT_RADIUS_METERS))
        except (TypeError, ValueError):
            return DEFAULT_RADIUS_METERS

        if radius < MIN_RADIUS_METERS or radius > MAX_RADIUS_METERS:
            return DEFAULT_RADIUS_METERS
        return radius

    def _query_signature(self) -> tuple[Any, ...]:
        return (self.area_mode, self.lat, self.lng, self.radius_meters)

    def _query_poly(self) -> str | None:
        if self.area_mode != AREA_MODE_RADIUS:
            return None
        return circle_polygon(self.lat, self.lng, self.radius_meters)

    def _query_area(self) -> dict[str, Any]:
        query_area: dict[str, Any] = {
            "mode": self.area_mode,
            "latitude": self.lat,
            "longitude": self.lng,
        }
        poly = self._query_poly()
        if poly:
            query_area.update(
                {
                    "radius_meters": self.radius_meters,
                    "polygon_points": POLYGON_POINTS,
                    "poly": poly,
                }
            )
        return query_area

    async def _get_crimes_for_month(self, month: str) -> list[dict]:
        if self.area_mode == AREA_MODE_RADIUS:
            poly = self._query_poly()
            if poly is None:
                return []
            return await self.client.get_crimes_street_poly(
                poly, category="all-crime", date_str=month
            )

        return await self.client.get_crimes_street(
            self.lat, self.lng, category="all-crime", date_str=month
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Daily lightweight check; only fully refetch when data or area changed."""
        try:
            fresh = await self.client.get_crime_last_updated()
            latest_date = (fresh or {}).get("date", "")
            query_signature = self._query_signature()

            if (
                latest_date
                and latest_date == self._last_data_date
                and query_signature == self._last_query_signature
                and self.data
            ):
                _LOGGER.debug(
                    "Police.uk data unchanged for query %s; skipping full fetch",
                    query_signature,
                )
                return self.data

            result = await self._fetch_all(prefetched_last_updated=fresh)
            self._last_data_date = latest_date
            self._last_query_signature = query_signature
            return result
        except UKPoliceApiError as err:
            raise UpdateFailed(f"Error communicating with Police.uk API: {err}") from err

    async def _fetch_all(
        self,
        prefetched_last_updated: dict | None = None,
    ) -> dict[str, Any]:
        """Fetch latest and historical crime data for the configured area."""
        data: dict[str, Any] = {}
        data["crime_last_updated"] = prefetched_last_updated

        data_month = self.client.latest_month_from_last_updated(prefetched_last_updated)
        data_month_fallback = False
        if data_month is None:
            data_month = self.client.fallback_latest_month()
            data_month_fallback = True

        data["data_month"] = data_month
        data["data_month_fallback"] = data_month_fallback
        data["query_area"] = self._query_area()

        try:
            latest_crimes = await self._get_crimes_for_month(data_month)
        except UKPoliceApiError as err:
            _LOGGER.warning("Failed to fetch crimes_street for %s: %s", data_month, err)
            latest_crimes = []

        data["crimes_street"] = latest_crimes or []
        await asyncio.sleep(_INTER_REQUEST_DELAY)

        month_strings = self.client.month_strings(self.crime_months, data_month)
        monthly_crimes: list[list[dict]] = []
        for month in month_strings:
            if month == data_month:
                crimes = latest_crimes
            else:
                try:
                    crimes = await self._get_crimes_for_month(month)
                except UKPoliceApiError as err:
                    _LOGGER.warning("Failed to fetch crimes for month %s: %s", month, err)
                    crimes = []
                await asyncio.sleep(_INTER_REQUEST_DELAY)
            monthly_crimes.append(crimes or [])

        data["monthly_crimes"] = monthly_crimes
        data["month_strings"] = month_strings
        data["computed"] = self._compute_stats(data)
        return data

    def _compute_stats(self, data: dict[str, Any]) -> dict[str, Any]:
        """Pre-compute sensor-friendly raw counts and incident attributes."""
        crimes = data.get("crimes_street") or []
        month_strings = data.get("month_strings") or []
        monthly_crimes = data.get("monthly_crimes") or []

        category_counts = {category: 0 for category in CRIME_CATEGORIES if category != "all-crime"}
        counted_categories: Counter = Counter(
            crime.get("category", "other-crime") for crime in crimes
        )
        category_counts.update(dict(counted_categories))

        monthly_counts = {
            month: len(monthly_crimes[index]) if index < len(monthly_crimes) else 0
            for index, month in enumerate(month_strings)
        }

        category_monthly_counts: dict[str, dict[str, int]] = {
            category: {month: 0 for month in month_strings}
            for category in CRIME_CATEGORIES
            if category != "all-crime"
        }
        for index, month in enumerate(month_strings):
            month_crimes = monthly_crimes[index] if index < len(monthly_crimes) else []
            month_counter = Counter(
                crime.get("category", "other-crime") for crime in month_crimes
            )
            for category in category_monthly_counts:
                category_monthly_counts[category][month] = month_counter.get(category, 0)

        incidents_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
        approximate_counts: dict[str, Counter] = {
            category: Counter()
            for category in CRIME_CATEGORIES
            if category != "all-crime"
        }
        latest_incidents: list[dict[str, Any]] = []

        for crime in crimes:
            normalized = normalize_incident(crime)
            category = normalized["category"]
            incidents_by_category[category].append(normalized)
            latest_incidents.append(normalized)
            approximate_counts.setdefault(category, Counter())[
                normalized["approximate_location"] or "Unknown"
            ] += 1

        return {
            "data_month": data.get("data_month", ""),
            "data_month_fallback": data.get("data_month_fallback", False),
            "total_crimes": len(crimes),
            "crime_counts_by_category": category_counts,
            "monthly_counts": monthly_counts,
            "latest_incidents": latest_incidents[:_TOTAL_INCIDENT_CAP],
            "latest_incident_count": len(latest_incidents),
            "latest_incidents_truncated": len(latest_incidents) > _TOTAL_INCIDENT_CAP,
            "category_monthly_counts": category_monthly_counts,
            "category_incidents": {
                category: incidents[:_CATEGORY_INCIDENT_CAP]
                for category, incidents in incidents_by_category.items()
            },
            "category_incident_counts": {
                category: len(incidents)
                for category, incidents in incidents_by_category.items()
            },
            "category_incidents_truncated": {
                category: len(incidents) > _CATEGORY_INCIDENT_CAP
                for category, incidents in incidents_by_category.items()
            },
            "category_approximate_counts": {
                category: dict(counts)
                for category, counts in approximate_counts.items()
            },
        }


def normalize_incident(crime: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, stable incident object for HA state attributes."""
    location = crime.get("location") or {}
    street = location.get("street") or {}
    outcome = crime.get("outcome_status") or {}
    category = crime.get("category") or "other-crime"

    latitude = _float_or_none(location.get("latitude"))
    longitude = _float_or_none(location.get("longitude"))

    return {
        "id": str(crime.get("id", "")),
        "persistent_id": crime.get("persistent_id") or "",
        "category": category,
        "category_name": CRIME_CATEGORIES.get(
            category, category.replace("-", " ").title()
        ),
        "month": crime.get("month", ""),
        "approximate_location": street.get("name", ""),
        "latitude": latitude,
        "longitude": longitude,
        "outcome": outcome.get("category", "") if isinstance(outcome, dict) else "",
    }


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
