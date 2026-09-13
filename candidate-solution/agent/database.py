"""
Database layer for Agent Service - Bronze Layer Persistence.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("agent.database")


class AgentDatabase:
    """Manages PostgreSQL connection and Bronze Layer persistence."""

    def __init__(self):
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.db = os.getenv("POSTGRES_DB", "gen_ai_agent_db")
        self.user = os.getenv("POSTGRES_USER", "agent_user")
        self.password = os.getenv("POSTGRES_PASSWORD", "agent_password")
        self._conn = None

    def get_connection(self):
        """Retrieve active database connection or establish new one."""
        if self._conn is None or self._conn.closed != 0:
            try:
                self._conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    dbname=self.db,
                    user=self.user,
                    password=self.password,
                    connect_timeout=10,
                )
                self._conn.autocommit = True
            except Exception as e:
                logger.error(f"Error connecting to PostgreSQL ({self.host}:{self.port}/{self.db}): {e}")
                raise
        return self._conn

    def insert_interaction(
        self,
        transaction_id: str,
        user_id: str,
        timestamp: datetime,
        user_query: str,
        agent_response: Optional[str] = None,
        llm_model: Optional[str] = None,
        tokens_used: int = 0,
        response_time_ms: int = 0,
        sentiment: Optional[str] = None,
        urgency_level: Optional[str] = None,
        raw_metadata: Optional[Dict[str, Any]] = None,
        interaction_id: Optional[str] = None,
    ) -> str:
        """
        Persist raw transaction interaction into the Bronze layer (agent_interactions).

        Returns:
            The generated or assigned interaction_id (UUID).
        """
        interaction_uuid = interaction_id or str(uuid.uuid4())
        conn = self.get_connection()

        query = """
            INSERT INTO agent_interactions (
                interaction_id,
                transaction_id,
                user_id,
                timestamp,
                user_query,
                agent_response,
                llm_model,
                tokens_used,
                response_time_ms,
                sentiment,
                urgency_level,
                raw_metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING interaction_id;
        """

        raw_json = json.dumps(raw_metadata or {})
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    interaction_uuid,
                    transaction_id,
                    user_id,
                    timestamp,
                    user_query,
                    agent_response,
                    llm_model,
                    tokens_used,
                    response_time_ms,
                    sentiment,
                    urgency_level,
                    raw_json,
                ),
            )
            inserted_id = cur.fetchone()[0]
            logger.info(
                f"Persisted to Bronze (agent_interactions): id={inserted_id}, txn={transaction_id}"
            )
            return str(inserted_id)

    def test_connection(self) -> bool:
        """Verify connectivity to PostgreSQL."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone()[0] == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
