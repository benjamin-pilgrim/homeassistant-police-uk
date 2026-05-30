"""DataUpdateCoordinator for UK Police integration."""
from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import UKPoliceApiClient, UKPoliceApiError
from .const import (
    CONF_CRIME_MONTHS,
    CONF_FORCE,
    CONF_INCLUDE_STOP_SEARCH,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NEIGHBOURHOOD,
    DEFAULT_CRIME_MONTHS,
    DEFAULT_INCLUDE_STOP_SEARCH,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

# Delay between sequential API calls to avoid 429 rate limiting
_INTER_REQUEST_DELAY = 2.0  # seconds


def _strip_html(text: str | None) -> str:
    """Remove HTML tags and normalise whitespace/newlines from API text."""
    if not text:
        return ""
    # Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", "", text)
    # Collapse newlines, tabs and multiple spaces to a single space
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()

_LOGGER = logging.getLogger(__name__)


class UKPoliceDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetch and cache all UK Police data for one neighbourhood entry."""

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

    @property
    def include_stop_search(self) -> bool:
        return self.entry.options.get(CONF_INCLUDE_STOP_SEARCH, DEFAULT_INCLUDE_STOP_SEARCH)

    @property
    def crime_months(self) -> int:
        return self.entry.options.get(CONF_CRIME_MONTHS, DEFAULT_CRIME_MONTHS)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data from the UK Police API."""
        try:
            return await self._fetch_all()
        except UKPoliceApiError as err:
            raise UpdateFailed(f"Error communicating with UK Police API: {err}") from err

    async def _fetch_all(self) -> dict[str, Any]:
        """Run API calls in small sequential batches to avoid 429 rate limiting."""
        date_str = self.client.latest_month()
        data: dict[str, Any] = {}

        # --- Batch 1: neighbourhood metadata – fully sequential to avoid 429 ---
        _nb1_calls = [
            ("neighbourhood_detail",    self.client.get_neighbourhood_detail(self.force_id, self.neighbourhood_id)),
            ("neighbourhood_team",      self.client.get_neighbourhood_team(self.force_id, self.neighbourhood_id)),
            ("neighbourhood_events",    self.client.get_neighbourhood_events(self.force_id, self.neighbourhood_id)),
            ("neighbourhood_priorities",self.client.get_neighbourhood_priorities(self.force_id, self.neighbourhood_id)),
            ("neighbourhood_boundary",  self.client.get_neighbourhood_boundary(self.force_id, self.neighbourhood_id)),
        ]
        for key, coro in _nb1_calls:
            try:
                data[key] = await coro
            except UKPoliceApiError as err:
                _LOGGER.warning("Failed to fetch %s: %s", key, err)
                data[key] = None if key == "neighbourhood_detail" else []
            await asyncio.sleep(_INTER_REQUEST_DELAY)

        # --- Batch 2: force metadata + crime freshness – sequential ---
        for key, coro in [
            ("force_detail",      self.client.get_force_detail(self.force_id)),
            ("crime_last_updated", self.client.get_crime_last_updated()),
        ]:
            try:
                data[key] = await coro
            except UKPoliceApiError as err:
                _LOGGER.warning("Failed to fetch %s: %s", key, err)
                data[key] = None
            await asyncio.sleep(_INTER_REQUEST_DELAY)

        # --- Batch 3: street crimes for latest month ---
        try:
            data["crimes_street"] = await self.client.get_crimes_street(
                self.lat, self.lng, category="all-crime", date_str=date_str
            ) or []
        except UKPoliceApiError as err:
            _LOGGER.warning("Failed to fetch crimes_street: %s", err)
            data["crimes_street"] = []

        await asyncio.sleep(_INTER_REQUEST_DELAY)

        # --- Batch 4: outcomes ---
        try:
            data["outcomes_at_location"] = await self.client.get_outcomes_at_location(
                self.lat, self.lng, date_str=date_str
            ) or []
        except UKPoliceApiError as err:
            _LOGGER.warning("Failed to fetch outcomes_at_location: %s", err)
            data["outcomes_at_location"] = []

        await asyncio.sleep(_INTER_REQUEST_DELAY)

        # --- Batch 5: stop & search (optional) ---
        if self.include_stop_search:
            try:
                data["stop_search"] = await self.client.get_stop_and_search_by_area(
                    self.lat, self.lng, date_str=date_str
                ) or []
            except UKPoliceApiError as err:
                _LOGGER.warning("Failed to fetch stop_search: %s", err)
                data["stop_search"] = []
        else:
            data["stop_search"] = []

        await asyncio.sleep(_INTER_REQUEST_DELAY)

        # --- Batch 6: monthly crime history (one request per month, sequential) ---
        month_strings = self.client.month_strings(self.crime_months)
        monthly_crimes: list[list[dict]] = []
        for m in month_strings:
            try:
                crimes = await self.client.get_crimes_street(
                    self.lat, self.lng, category="all-crime", date_str=m
                ) or []
                monthly_crimes.append(crimes)
            except UKPoliceApiError as err:
                _LOGGER.warning("Failed to fetch crimes for month %s: %s", m, err)
                monthly_crimes.append([])
            await asyncio.sleep(_INTER_REQUEST_DELAY)

        data["monthly_crimes"] = monthly_crimes
        data["month_strings"] = month_strings

        # Pre-compute aggregated stats
        data["computed"] = self._compute_stats(data)

        return data

    def _compute_stats(self, data: dict[str, Any]) -> dict[str, Any]:
        """Pre-compute sensor-friendly statistics from raw API data."""
        stats: dict[str, Any] = {}

        # --- Crime totals by category (latest month) ---
        crimes = data.get("crimes_street") or []
        category_counts: Counter = Counter()
        for crime in crimes:
            category_counts[crime.get("category", "other-crime")] += 1
        stats["crime_counts_by_category"] = dict(category_counts)
        stats["total_crimes"] = len(crimes)

        # --- Crime trend (total per month across history) ---
        monthly_totals = [len(m) for m in (data.get("monthly_crimes") or [])]
        stats["monthly_crime_totals"] = monthly_totals
        stats["crime_trend"] = _trend_label(monthly_totals)

        # --- Outcomes ---
        # API returns: [{"crime": {...}, "outcomes": [{"category": {"code": ...}, "date": ...}]}]
        outcomes = data.get("outcomes_at_location") or []
        outcome_counts: Counter = Counter()
        for item in outcomes:
            for outcome_entry in (item.get("outcomes") or []):
                code = (outcome_entry.get("category") or {}).get("code", "unknown")
                outcome_counts[code] += 1
        stats["outcome_counts"] = dict(outcome_counts)

        # --- Stop & Search stats ---
        stop_search = data.get("stop_search") or []
        stats["total_stop_search"] = len(stop_search)
        ss_object_counts: Counter = Counter()
        ss_outcome_counts: Counter = Counter()
        ss_self_defined_ethnicity: Counter = Counter()
        ss_age_range: Counter = Counter()
        ss_gender: Counter = Counter()
        for ss in stop_search:
            obj = ss.get("object_of_search") or "unknown"
            ss_object_counts[obj] += 1
            outcome = ss.get("outcome") or "unknown"
            ss_outcome_counts[outcome] += 1
            ethnicity = ss.get("self_defined_ethnicity") or "unknown"
            ss_self_defined_ethnicity[ethnicity] += 1
            age = ss.get("age_range") or "unknown"
            ss_age_range[age] += 1
            gender = ss.get("gender") or "unknown"
            ss_gender[gender] += 1

        stats["stop_search_by_object"] = dict(ss_object_counts)
        stats["stop_search_by_outcome"] = dict(ss_outcome_counts)
        stats["stop_search_by_ethnicity"] = dict(ss_self_defined_ethnicity)
        stats["stop_search_by_age"] = dict(ss_age_range)
        stats["stop_search_by_gender"] = dict(ss_gender)

        # --- Neighbourhood team ---
        team = data.get("neighbourhood_team") or []
        stats["team_count"] = len(team)
        stats["team_names"] = [
            f"{p.get('rank', '')} {p.get('name', '')}" .strip() for p in team
        ]

        # --- Events ---
        events = data.get("neighbourhood_events") or []
        stats["upcoming_events_count"] = len(events)
        stats["has_upcoming_events"] = len(events) > 0
        stats["next_event_title"] = _strip_html(events[0].get("title", "")) if events else ""
        stats["next_event_date"] = events[0].get("start_date", "") if events else ""

        # --- Priorities ---
        priorities = data.get("neighbourhood_priorities") or []
        stats["priorities_count"] = len(priorities)
        stats["priority_issues"] = [_strip_html(p.get("issue", "")) for p in priorities]

        # --- Force info ---
        force = data.get("force_detail") or {}
        stats["force_name"] = force.get("name", "")
        stats["force_telephone"] = force.get("telephone", "")
        stats["force_url"] = force.get("url", "")
        stats["force_description"] = _strip_html(force.get("description", ""))

        # --- Last updated ---
        last_updated = data.get("crime_last_updated") or {}
        stats["data_last_updated"] = last_updated.get("date", "")

        return stats


def _trend_label(monthly_totals: list[int]) -> str:
    """Return 'rising', 'falling', 'stable', or 'unknown' based on monthly totals."""
    if len(monthly_totals) < 2:
        return "unknown"
    # Compare most recent vs oldest in set
    recent = monthly_totals[0]
    oldest = monthly_totals[-1]
    diff = recent - oldest
    if abs(diff) <= max(1, oldest * 0.05):
        return "stable"
    return "rising" if diff > 0 else "falling"
