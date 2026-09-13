"""
Unit tests for Agent input/output schemas and validation rules.
Ensures incoming transactions from Transaction Service conform to expected structure.
"""

import pytest
from pydantic import ValidationError
from agent.main import TransactionRequest


class TestTransactionRequestValidation:
    """Tests for the TransactionRequest Pydantic schema."""

    def test_valid_payload_minimal(self):
        """A payload with all required fields should validate correctly."""
        data = {
            "transaction_id": "txn_test_001",
            "user_id": "user_abc123",
            "timestamp": "2026-09-13T12:00:00Z",
            "query": "¿Cuál es el clima en Bogotá?",
        }
        payload = TransactionRequest(**data)
        assert payload.transaction_id == "txn_test_001"
        assert payload.user_id == "user_abc123"
        assert payload.query == "¿Cuál es el clima en Bogotá?"
        assert payload.llm_model == "gpt-4"  # Default value
        assert payload.tokens_used == 0  # Default value

    def test_valid_payload_with_metadata(self):
        """Payload with location metadata should preserve coordinates and city."""
        data = {
            "transaction_id": "txn_test_002",
            "user_id": "user_xyz789",
            "timestamp": "2026-09-13T12:00:00Z",
            "query": "Temperatura y viento",
            "location_metadata": {
                "latitude": 4.7110,
                "longitude": -74.0721,
                "city": "Bogotá",
            },
        }
        payload = TransactionRequest(**data)
        assert payload.location_metadata is not None
        assert payload.location_metadata.get("city") == "Bogotá"
        assert payload.location_metadata.get("latitude") == 4.7110

    def test_missing_transaction_id_raises_error(self):
        """Missing transaction_id must raise a ValidationError."""
        data = {
            "user_id": "user_test",
            "timestamp": "2026-09-13T12:00:00Z",
            "query": "Consulta sin ID",
        }
        with pytest.raises(ValidationError):
            TransactionRequest(**data)

    def test_missing_query_raises_error(self):
        """Missing query must raise a ValidationError."""
        data = {
            "transaction_id": "txn_no_query",
            "user_id": "user_test",
            "timestamp": "2026-09-13T12:00:00Z",
        }
        with pytest.raises(ValidationError):
            TransactionRequest(**data)
