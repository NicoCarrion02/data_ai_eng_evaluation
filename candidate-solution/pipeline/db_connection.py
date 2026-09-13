"""
Database connection utilities for the ETL Pipeline.
"""

import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

load_dotenv()


class PipelineDB:
    """Provides DB connectivity for pandas and SQLAlchemy operations."""

    def __init__(self):
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.db = os.getenv("POSTGRES_DB", "gen_ai_agent_db")
        self.user = os.getenv("POSTGRES_USER", "agent_user")
        self.password = os.getenv("POSTGRES_PASSWORD", "agent_password")

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    def get_engine(self) -> Engine:
        """Create a SQLAlchemy engine."""
        return create_engine(self.connection_string, pool_pre_ping=True)

    def get_psycopg2_connection(self):
        """Create a raw psycopg2 connection."""
        conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.db,
            user=self.user,
            password=self.password,
            connect_timeout=10,
        )
        conn.autocommit = True
        return conn
