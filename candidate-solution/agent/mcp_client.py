"""
MCP Client for the Agent Service.
Connects to the FastMCP / MCPServer over SSE transport to invoke tools.
Provides graceful fallback to direct location service if needed.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger("agent.mcp_client")


class AgentMCPClient:
    """Invokes location enrichment tools via MCP Server."""

    def __init__(self):
        mcp_host = os.getenv("MCP_SERVER_HOST", "localhost")
        mcp_port = os.getenv("MCP_SERVER_PORT", "8003")
        env_url = os.getenv("MCP_SERVER_URL")
        self.mcp_base_url = (env_url or f"http://{mcp_host}:{mcp_port}").rstrip("/")
        self.sse_endpoint = f"{self.mcp_base_url}/sse"

        # Direct fallback URL to location service
        loc_host = os.getenv("LOCATION_SERVICE_HOST", "localhost")
        loc_port = os.getenv("LOCATION_SERVICE_PORT", "8001")
        loc_url = os.getenv("LOCATION_SERVICE_URL")
        self.location_service_url = (loc_url or f"http://{loc_host}:{loc_port}").rstrip("/")

    async def call_mcp_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Call tool via official MCP SSE transport."""
        args = arguments or {}
        logger.info(f"Calling MCP Tool '{tool_name}' via SSE ({self.sse_endpoint})")
        try:
            async with sse_client(self.sse_endpoint, timeout=5.0) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=args)
                    # Parse MCP tool result content
                    if hasattr(result, "content") and result.content:
                        content_item = result.content[0]
                        if hasattr(content_item, "text"):
                            try:
                                return json.loads(content_item.text)
                            except Exception:
                                return content_item.text
                        return content_item
                    return result
        except Exception as e:
            logger.warning(f"MCP SSE invocation failed for '{tool_name}': {e}. Using direct location fallback.")
            return await self._fallback_direct_call(tool_name, args)

    async def _fallback_direct_call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Direct REST fallback to Location Service."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                if tool_name == "get_all_locations":
                    resp = await client.get(f"{self.location_service_url}/locations")
                    return resp.json()
                elif tool_name == "get_location_by_id":
                    loc_id = arguments.get("location_id", "")
                    resp = await client.get(f"{self.location_service_url}/locations/{loc_id}")
                    return resp.json()
                elif tool_name == "get_location_by_city":
                    city = arguments.get("city", "")
                    resp = await client.get(f"{self.location_service_url}/locations/by-city/{city}")
                    return resp.json()
                elif tool_name == "get_location_by_coordinates":
                    lat = arguments.get("latitude")
                    lon = arguments.get("longitude")
                    tol = arguments.get("tolerance", 0.5)
                    resp = await client.get(
                        f"{self.location_service_url}/locations/by-coordinates",
                        params={"latitude": lat, "longitude": lon, "tolerance": tol},
                    )
                    return resp.json()
                elif tool_name == "get_locations_by_country":
                    country = arguments.get("country", "")
                    resp = await client.get(f"{self.location_service_url}/locations/by-country/{country}")
                    return resp.json()
            except Exception as e:
                logger.error(f"Fallback direct call also failed: {e}")
                return {"error": str(e)}

    async def enrich_location(
        self, city: Optional[str] = None, latitude: Optional[float] = None, longitude: Optional[float] = None
    ) -> Dict[str, Any]:
        """Convenience method to query location data using city or coordinates."""
        if city:
            res = await self.call_mcp_tool("get_location_by_city", {"city": city})
            if isinstance(res, dict) and not res.get("error"):
                return res

        if latitude is not None and longitude is not None:
            res = await self.call_mcp_tool(
                "get_location_by_coordinates",
                {"latitude": latitude, "longitude": longitude, "tolerance": 0.5},
            )
            if isinstance(res, dict) and not res.get("error"):
                return res

        # Default search
        all_locs = await self.call_mcp_tool("get_all_locations")
        if isinstance(all_locs, list) and len(all_locs) > 0:
            return all_locs[0]

        return {}
