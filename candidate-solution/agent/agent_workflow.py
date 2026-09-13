"""
Agent Workflow - Orchestrates MCP enrichment, LLM reasoning, and Bronze persistence
using LangGraph StateGraph architecture.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from agent.database import AgentDatabase
from agent.llm_service import LLMService
from agent.mcp_client import AgentMCPClient

logger = logging.getLogger("agent.workflow")


class AgentState(TypedDict):
    """LangGraph state representation for the transaction processing agent."""

    transaction_id: str
    user_id: str
    timestamp: datetime
    query: str
    llm_model: str
    tokens_used: int
    input_response_time: int
    start_time: float
    response_time_ms: int
    location_metadata: Dict[str, Any]
    enriched_location: Optional[Dict[str, Any]]
    sentiment: Optional[str]
    urgency_level: Optional[str]
    agent_response: Optional[str]
    interaction_id: Optional[str]
    status: str


class AgentWorkflow:
    """LangGraph-powered agent processor for incoming transactions."""

    def __init__(self):
        self.mcp_client = AgentMCPClient()
        self.llm_service = LLMService()
        self.db = AgentDatabase()
        self.graph = self._build_langgraph()

    def _build_langgraph(self):
        """Construct and compile the LangGraph StateGraph."""
        logger.info("Initializing LangGraph StateGraph for GeoAI Agent...")
        workflow = StateGraph(AgentState)

        # Register nodes
        workflow.add_node("enrich_context", self.enrich_context_node)
        workflow.add_node("analyze_llm", self.analyze_llm_node)
        workflow.add_node("persist_bronze", self.persist_bronze_node)

        # Define graph edges (START -> enrich -> analyze -> persist -> END)
        workflow.add_edge(START, "enrich_context")
        workflow.add_edge("enrich_context", "analyze_llm")
        workflow.add_edge("analyze_llm", "persist_bronze")
        workflow.add_edge("persist_bronze", END)

        compiled_graph = workflow.compile()
        logger.info("LangGraph StateGraph successfully compiled.")
        return compiled_graph

    async def enrich_context_node(self, state: AgentState) -> Dict[str, Any]:
        """
        LangGraph Node 1: MCP Context Enrichment.
        Queries the MCP Server via SSE to retrieve weather, demographic and observation context.
        """
        logger.info(f"[LangGraph Node: enrich_context] Txn {state['transaction_id']}")
        location_meta = state.get("location_metadata", {})
        city = location_meta.get("city")
        lat = location_meta.get("latitude")
        lon = location_meta.get("longitude")

        enriched_data = await self.mcp_client.enrich_location(
            city=city, latitude=lat, longitude=lon
        )
        return {"enriched_location": enriched_data}

    async def analyze_llm_node(self, state: AgentState) -> Dict[str, Any]:
        """
        LangGraph Node 2: LLM Reasoning.
        Analyzes sentiment, detects urgency level, and synthesizes contextual response.
        """
        logger.info(f"[LangGraph Node: analyze_llm] Txn {state['transaction_id']}")
        sentiment, urgency, agent_response = await self.llm_service.analyze_and_respond(
            query=state["query"],
            location_data=state.get("enriched_location"),
            model_name=state.get("llm_model", "gpt-4"),
        )
        return {
            "sentiment": sentiment,
            "urgency_level": urgency,
            "agent_response": agent_response,
        }

    async def persist_bronze_node(self, state: AgentState) -> Dict[str, Any]:
        """
        LangGraph Node 3: Bronze Layer Persistence.
        Stores raw transaction data and enriched metadata in agent_interactions table.
        """
        logger.info(f"[LangGraph Node: persist_bronze] Txn {state['transaction_id']}")
        elapsed_ms = int((time.time() - state["start_time"]) * 1000) + state["input_response_time"]

        combined_raw_metadata = {
            "original_location": state.get("location_metadata", {}),
            "mcp_enriched": state.get("enriched_location", {}),
        }

        try:
            interaction_id = self.db.insert_interaction(
                transaction_id=state["transaction_id"],
                user_id=state["user_id"],
                timestamp=state["timestamp"],
                user_query=state["query"],
                agent_response=state.get("agent_response"),
                llm_model=state.get("llm_model"),
                tokens_used=state.get("tokens_used", 0),
                response_time_ms=elapsed_ms,
                sentiment=state.get("sentiment"),
                urgency_level=state.get("urgency_level"),
                raw_metadata=combined_raw_metadata,
            )
            status = "success"
        except Exception as e:
            logger.error(f"Failed to persist interaction in Bronze layer: {e}")
            interaction_id = None
            status = "failed"

        return {
            "interaction_id": interaction_id,
            "response_time_ms": elapsed_ms,
            "status": status,
        }

    async def process_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke the compiled LangGraph workflow with an incoming transaction.
        """
        raw_ts = transaction.get("timestamp")
        if isinstance(raw_ts, str):
            try:
                ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            except Exception:
                ts = datetime.utcnow()
        elif isinstance(raw_ts, datetime):
            ts = raw_ts
        else:
            ts = datetime.utcnow()

        initial_state: AgentState = {
            "transaction_id": transaction["transaction_id"],
            "user_id": transaction["user_id"],
            "timestamp": ts,
            "query": transaction.get("query", ""),
            "llm_model": transaction.get("llm_model", "gpt-4"),
            "tokens_used": int(transaction.get("tokens_used", 100)),
            "input_response_time": int(transaction.get("response_time_ms", 500)),
            "start_time": time.time(),
            "response_time_ms": 0,
            "location_metadata": transaction.get("location_metadata", {}),
            "enriched_location": None,
            "sentiment": None,
            "urgency_level": None,
            "agent_response": None,
            "interaction_id": None,
            "status": "pending",
        }

        # Execute through LangGraph
        final_state = await self.graph.ainvoke(initial_state)

        return {
            "status": final_state.get("status", "failed"),
            "interaction_id": final_state.get("interaction_id"),
            "transaction_id": final_state["transaction_id"],
            "sentiment": final_state.get("sentiment"),
            "urgency_level": final_state.get("urgency_level"),
            "agent_response": final_state.get("agent_response"),
            "response_time_ms": final_state.get("response_time_ms"),
            "enriched_location": final_state.get("enriched_location"),
        }
