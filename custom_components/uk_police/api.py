"""UK Police API client."""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import aiohttp

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30


class UKPoliceApiError(Exception):
    """Raised when the API returns an error."""


class UKPoliceApiClient:
    """Async client for the UK Police data API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, endpoint: str, params: dict | None = None) -> Any:
        """Perform a GET request and return JSON."""
        url = f"{API_BASE_URL}/{endpoint}"
        try:
            async with self._session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
            ) as resp:
                if resp.status == 404:
                    return None
                if resp.status != 200:
                    text = await resp.text()
                    raise UKPoliceApiError(
                        f"API request to {url} failed with status {resp.status}: {text}"
                    )
                return await resp.json()
        except asyncio.TimeoutError as err:
            raise UKPoliceApiError(f"Timeout connecting to UK Police API: {url}") from err
        except aiohttp.ClientError as err:
            raise UKPoliceApiError(f"Error connecting to UK Police API: {err}") from err

    # ------------------------------------------------------------------
    # Force / Neighbourhood discovery
    # ------------------------------------------------------------------

    async def get_forces(self) -> list[dict]:
        """Return list of all police forces: [{id, name}]."""
        data = await self._get("forces")
        return data or []

    async def get_force_detail(self, force_id: str) -> dict | None:
        """Return detailed information about a specific force."""
        return await self._get(f"forces/{force_id}")

    async def get_neighbourhoods(self, force_id: str) -> list[dict]:
        """Return list of neighbourhoods for a force: [{id, name}]."""
        data = await self._get(f"{force_id}/neighbourhoods")
        return data or []

    async def get_neighbourhood_detail(self, force_id: str, neighbourhood_id: str) -> dict | None:
        """Return detailed info for a neighbourhood (includes boundary, centre, officers)."""
        return await self._get(f"{force_id}/{neighbourhood_id}")

    async def get_neighbourhood_boundary(self, force_id: str, neighbourhood_id: str) -> list[dict]:
        """Return list of lat/lng points forming the neighbourhood boundary."""
        data = await self._get(f"{force_id}/{neighbourhood_id}/boundary")
        return data or []

    async def get_neighbourhood_team(self, force_id: str, neighbourhood_id: str) -> list[dict]:
        """Return list of officers for the neighbourhood team."""
        data = await self._get(f"{force_id}/{neighbourhood_id}/people")
        return data or []

    async def get_neighbourhood_events(self, force_id: str, neighbourhood_id: str) -> list[dict]:
        """Return upcoming neighbourhood events/meetings."""
        data = await self._get(f"{force_id}/{neighbourhood_id}/events")
        return data or []

    async def get_neighbourhood_priorities(self, force_id: str, neighbourhood_id: str) -> list[dict]:
        """Return neighbourhood policing priorities."""
        data = await self._get(f"{force_id}/{neighbourhood_id}/priorities")
        return data or []

    async def locate_neighbourhood(self, lat: float, lng: float) -> dict | None:
        """Locate a neighbourhood by lat/lng. Returns {force, neighbourhood}."""
        return await self._get("locate-neighbourhood", {"q": f"{lat},{lng}"})

    # ------------------------------------------------------------------
    # Crimes
    # ------------------------------------------------------------------

    async def get_crimes_at_location(
        self, lat: float, lng: float, date_str: str | None = None
    ) -> list[dict]:
        """Return crimes at a specific lat/lng point."""
        params: dict = {"lat": lat, "lng": lng}
        if date_str:
            params["date"] = date_str
        data = await self._get("crimes-at-location", params)
        return data or []

    async def get_crimes_street(
        self,
        lat: float,
        lng: float,
        category: str = "all-crime",
        date_str: str | None = None,
    ) -> list[dict]:
        """Return street-level crimes near a location."""
        params: dict = {"lat": lat, "lng": lng, "category": category}
        if date_str:
            params["date"] = date_str
        data = await self._get(f"crimes-street/{category}", params)
        return data or []

    async def get_crimes_no_location(
        self, force_id: str, category: str = "all-crime", date_str: str | None = None
    ) -> list[dict]:
        """Return crimes with no location for a force."""
        params: dict = {"force": force_id, "category": category}
        if date_str:
            params["date"] = date_str
        data = await self._get("crimes-no-location", params)
        return data or []

    async def get_crime_categories(self, date_str: str | None = None) -> list[dict]:
        """Return list of valid crime categories for a given date."""
        params: dict = {}
        if date_str:
            params["date"] = date_str
        data = await self._get("crime-categories", params)
        return data or []

    async def get_crime_last_updated(self) -> dict | None:
        """Return date when crime data was last updated."""
        return await self._get("crime-last-updated")

    async def get_outcomes_for_crime(self, crime_persistent_id: str) -> dict | None:
        """Return outcomes (case history) for a specific crime."""
        return await self._get(f"outcomes-for-crime/{crime_persistent_id}")

    async def get_outcomes_at_location(
        self, lat: float, lng: float, date_str: str | None = None
    ) -> list[dict]:
        """Return crime outcomes at a location."""
        params: dict = {"lat": lat, "lng": lng}
        if date_str:
            params["date"] = date_str
        data = await self._get("outcomes-at-location", params)
        return data or []

    # ------------------------------------------------------------------
    # Stop & Search
    # ------------------------------------------------------------------

    async def get_stop_and_search_by_area(
        self, lat: float, lng: float, date_str: str | None = None
    ) -> list[dict]:
        """Return stop & searches near a location."""
        params: dict = {"lat": lat, "lng": lng}
        if date_str:
            params["date"] = date_str
        data = await self._get("stops-street", params)
        return data or []

    async def get_stop_and_search_by_force(
        self, force_id: str, date_str: str | None = None
    ) -> list[dict]:
        """Return stop & searches for a force (force-level data)."""
        params: dict = {"force": force_id}
        if date_str:
            params["date"] = date_str
        data = await self._get("stops-force", params)
        return data or []

    async def get_stop_and_search_no_location(
        self, force_id: str, date_str: str | None = None
    ) -> list[dict]:
        """Return stop & searches with no location for a force."""
        params: dict = {"force": force_id}
        if date_str:
            params["date"] = date_str
        data = await self._get("stops-no-location", params)
        return data or []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def month_strings(months_back: int = 3) -> list[str]:
        """Return YYYY-MM strings going back N months from the latest available data month.

        The UK Police API is typically 2 months behind the current date, so we
        start from that latest available month rather than the current calendar month.
        """
        today = date.today()
        # Latest available month (2 months behind)
        latest_m = today.month - 2
        latest_y = today.year
        if latest_m <= 0:
            latest_m += 12
            latest_y -= 1

        result = []
        for i in range(months_back):
            m = latest_m - i
            y = latest_y
            while m <= 0:
                m += 12
                y -= 1
            result.append(f"{y}-{m:02d}")
        return result

    @staticmethod
    def latest_month() -> str:
        """Return the most recent complete month as YYYY-MM."""
        today = date.today()
        # Police data is ~2 months behind
        m = today.month - 2
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        return f"{y}-{m:02d}"
