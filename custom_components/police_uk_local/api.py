"""Police.uk API client."""
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
    """Async client for the Police.uk data API."""

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
            raise UKPoliceApiError(f"Timeout connecting to Police.uk API: {url}") from err
        except aiohttp.ClientError as err:
            raise UKPoliceApiError(f"Error connecting to Police.uk API: {err}") from err

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

    async def get_crimes_street_poly(
        self,
        poly: str,
        category: str = "all-crime",
        date_str: str | None = None,
    ) -> list[dict]:
        """Return street-level crimes inside a polygon."""
        params: dict = {"poly": poly}
        if date_str:
            params["date"] = date_str
        data = await self._get(f"crimes-street/{category}", params)
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def fallback_latest_month() -> str:
        """Return the heuristic latest available month as YYYY-MM."""
        today = date.today()
        m = today.month - 2
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        return f"{y}-{m:02d}"

    @staticmethod
    def latest_month_from_last_updated(last_updated: dict | None) -> str | None:
        """Return YYYY-MM from the Police.uk crime-last-updated response."""
        updated_date = (last_updated or {}).get("date")
        if isinstance(updated_date, str) and len(updated_date) >= 7:
            return updated_date[:7]
        return None
