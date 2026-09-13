"""
Unit tests for LocationClient and MCP tools logic.
Uses mocking to test HTTP responses without requiring the real Location Service container.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from mcp_server.location_client import LocationClient


@pytest.mark.asyncio
async def test_get_all_locations_mocked():
    """Verify that get_all_locations parses and returns the JSON list correctly."""
    mock_data = [
        {"location_id": "loc_cdmx_001", "city": "Ciudad de México", "country": "México"},
        {"location_id": "loc_tokyo_001", "city": "Tokyo", "country": "Japan"},
    ]

    client = LocationClient(base_url="http://mock-location-service:8001")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.get_all_locations()
        assert len(result) == 2
        assert result[0]["city"] == "Ciudad de México"
        assert result[1]["country"] == "Japan"


@pytest.mark.asyncio
async def test_get_location_by_city_mocked():
    """Verify that get_location_by_city calls the expected URL and returns data."""
    mock_city_data = {
        "location_id": "loc_cdmx_001",
        "city": "Ciudad de México",
        "weather": {"temperature": 22, "condition": "Soleado"},
    }

    client = LocationClient(base_url="http://mock-location-service:8001")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_city_data
    mock_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.get_location_by_city("Ciudad de México")
        assert result["location_id"] == "loc_cdmx_001"
        assert result["weather"]["temperature"] == 22
