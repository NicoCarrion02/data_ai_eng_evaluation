"""
HTTP Client for consuming the Location Service REST API.
"""

import os
from typing import Any, Dict, List, Optional
import httpx


class LocationClient:
    """Client for querying the Location Service."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0):
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            host = os.getenv("LOCATION_SERVICE_HOST", "localhost")
            port = os.getenv("LOCATION_SERVICE_PORT", "8001")
            env_url = os.getenv("LOCATION_SERVICE_URL")
            self.base_url = (env_url or f"http://{host}:{port}").rstrip("/")
        self.timeout = timeout

    async def get_all_locations(self) -> List[Dict[str, Any]]:
        """Retrieve all available locations."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/locations")
            response.raise_for_status()
            return response.json()

    async def get_location_by_id(self, location_id: str) -> Dict[str, Any]:
        """Retrieve location data by unique identifier (e.g. loc_cdmx_001)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/locations/{location_id}")
            response.raise_for_status()
            return response.json()

    async def get_location_by_city(self, city: str) -> Dict[str, Any]:
        """Retrieve location data by city name (case-insensitive)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/locations/by-city/{city}")
            response.raise_for_status()
            return response.json()

    async def get_location_by_coordinates(
        self, latitude: float, longitude: float, tolerance: float = 0.5
    ) -> Dict[str, Any]:
        """Find nearest location within spatial tolerance."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "tolerance": tolerance,
            }
            response = await client.get(
                f"{self.base_url}/locations/by-coordinates", params=params
            )
            response.raise_for_status()
            return response.json()

    async def get_locations_by_country(self, country: str) -> List[Dict[str, Any]]:
        """Retrieve all locations for a given country."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/locations/by-country/{country}")
            response.raise_for_status()
            return response.json()
