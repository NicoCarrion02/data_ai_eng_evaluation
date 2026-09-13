"""
FastAPI Agent Service - Entrypoint for receiving and processing transactions.
"""

import logging
import os
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent.agent_workflow import AgentWorkflow
from agent.database import AgentDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent.main")

app = FastAPI(
    title="GeoAI Analytics - Agent Recovery Service",
    description="Agent service receiving transactions, enriching via MCP, analyzing with LLM, and persisting in Bronze layer.",
    version="1.0.0",
)

workflow = AgentWorkflow()
db = AgentDatabase()


class LocationMetadata(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None


class TransactionRequest(BaseModel):
    transaction_id: str = Field(..., description="Unique transaction ID")
    user_id: str = Field(..., description="User identifier")
    timestamp: str = Field(..., description="ISO 8601 transaction timestamp")
    query: str = Field(..., description="User query prompt")
    llm_model: Optional[str] = Field("gpt-4", description="LLM model identifier")
    tokens_used: Optional[int] = Field(0, description="Tokens used")
    response_time_ms: Optional[int] = Field(0, description="Response time in ms")
    location_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "service": "GeoAI Agent Recovery Service",
        "status": "healthy",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check including database connection."""
    db_ok = db.test_connection()
    return {
        "service": "GeoAI Agent Recovery Service",
        "database_connected": db_ok,
        "status": "ready" if db_ok else "degraded",
    }


@app.post("/transactions", tags=["Transactions"])
async def receive_transaction(txn: TransactionRequest):
    """
    Ingest and process a transaction from Transaction Service.
    - Enriches with location context via MCP Server.
    - Evaluates sentiment and urgency level.
    - Persists interaction to Bronze Layer (agent_interactions).
    """
    try:
        result = await workflow.process_transaction(txn.model_dump())
        return result
    except Exception as e:
        logger.error(f"Error handling transaction {txn.transaction_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to process transaction: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_PORT", "8000"))
    logger.info(f"Starting Agent Service on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
