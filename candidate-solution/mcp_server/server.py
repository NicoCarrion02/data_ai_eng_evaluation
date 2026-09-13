"""
MCP Server implementation using official MCP SDK (MCPServer / FastMCP).
Exposes tools to consume and query the Location Service.
"""

import logging
import os
from typing import Any, Dict, List

# Compatible import across MCP 1.x and MCP 2.x
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = None

from mcp_server.location_client import LocationClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")

# Retrieve configuration from environment
MCP_HOST = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_SERVER_PORT", "8003"))

# Initialize FastMCP / MCPServer
mcp = FastMCP(
    name="GeoAILocationMCP",
    instructions=(
        "Official MCP Server for GeoAI Analytics. Provides tools to query "
        "and retrieve real-time location, weather, and demographic context."
    ),
)

# Initialize location API client
location_client = LocationClient()


@mcp.tool()
async def get_all_locations() -> List[Dict[str, Any]]:
    """
    Retrieve the full list of all 12 global locations with current weather and demographics.

    Returns:
        List of location objects containing coordinates, weather, demographics and observations.
    """
    logger.info("Executing MCP Tool: get_all_locations")
    try:
        return await location_client.get_all_locations()
    except Exception as e:
        logger.error(f"Error in get_all_locations: {e}")
        return [{"error": str(e)}]


@mcp.tool()
async def get_location_by_id(location_id: str) -> Dict[str, Any]:
    """
    Retrieve full location metadata by location identifier.

    Args:
        location_id: Unique location identifier (e.g., 'loc_cdmx_001', 'loc_tokyo_001').

    Returns:
        Location data object or error dictionary.
    """
    logger.info(f"Executing MCP Tool: get_location_by_id ({location_id})")
    try:
        return await location_client.get_location_by_id(location_id)
    except Exception as e:
        logger.error(f"Error in get_location_by_id: {e}")
        return {"error": str(e), "location_id": location_id}


@mcp.tool()
async def get_location_by_city(city: str) -> Dict[str, Any]:
    """
    Retrieve location data matching the given city name (case-insensitive).

    Args:
        city: City name (e.g., 'Ciudad de México', 'Tokyo', 'London', 'New York').

    Returns:
        Location data object or error dictionary.
    """
    logger.info(f"Executing MCP Tool: get_location_by_city ({city})")
    try:
        return await location_client.get_location_by_city(city)
    except Exception as e:
        logger.error(f"Error in get_location_by_city: {e}")
        return {"error": str(e), "city": city}


@mcp.tool()
async def get_location_by_coordinates(
    latitude: float, longitude: float, tolerance: float = 0.5
) -> Dict[str, Any]:
    """
    Retrieve nearest location within tolerance degrees for given latitude and longitude.

    Args:
        latitude: Latitude coordinate (-90 to 90).
        longitude: Longitude coordinate (-180 to 180).
        tolerance: Coordinate distance tolerance in degrees (default: 0.5).

    Returns:
        Nearest location data object or error dictionary.
    """
    logger.info(
        f"Executing MCP Tool: get_location_by_coordinates ({latitude}, {longitude}, tol={tolerance})"
    )
    try:
        return await location_client.get_location_by_coordinates(
            latitude=latitude, longitude=longitude, tolerance=tolerance
        )
    except Exception as e:
        logger.error(f"Error in get_location_by_coordinates: {e}")
        return {
            "error": str(e),
            "latitude": latitude,
            "longitude": longitude,
            "tolerance": tolerance,
        }


@mcp.tool()
async def get_locations_by_country(country: str) -> List[Dict[str, Any]]:
    """
    Retrieve all locations situated within a specific country (case-insensitive).

    Args:
        country: Country name (e.g., 'México', 'Japan', 'United States').

    Returns:
        List of location data objects or error dictionary.
    """
    logger.info(f"Executing MCP Tool: get_locations_by_country ({country})")
    try:
        return await location_client.get_locations_by_country(country)
    except Exception as e:
        logger.error(f"Error in get_locations_by_country: {e}")
        return [{"error": str(e), "country": country}]


def get_asgi_app():
    """Build ASGI application supporting MCP SSE transport and health checks."""
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    # Allow container network hostnames (e.g. mcp-server:8003) in Docker
    try:
        from mcp.server.transport_security import TransportSecuritySettings
        transport_sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        app = mcp.sse_app(transport_security=transport_sec)
    except Exception:
        app = mcp.sse_app()

    async def health(request):
        return JSONResponse({
            "service": "GeoAI Location MCP Server",
            "status": "healthy",
            "protocol": "mcp-sse",
            "port": MCP_PORT,
            "tools": [
                "get_all_locations",
                "get_location_by_id",
                "get_location_by_city",
                "get_location_by_coordinates",
                "get_locations_by_country",
            ],
        })

    # Add health route to starlette app
    app.routes.append(Route("/", endpoint=health, methods=["GET"]))
    app.routes.append(Route("/health", endpoint=health, methods=["GET"]))
    return app


def run_server():
    """Run the MCP server with SSE transport via Uvicorn."""
    import uvicorn
    logger.info(f"Starting GeoAI MCP Server on {MCP_HOST}:{MCP_PORT} (transport=sse)...")
    app = get_asgi_app()
    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)


if __name__ == "__main__":
    run_server()
