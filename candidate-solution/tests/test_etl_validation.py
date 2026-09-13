"""
Unit tests for ETL validation rules and feature engineering.
Tests Bronze -> Silver data quality checks and Silver -> Gold query classification.
"""

from datetime import datetime
import pytest
from pipeline.bronze_to_silver import BronzeToSilverTransformer
from pipeline.silver_to_gold import SilverToGoldTransformer


class TestBronzeToSilverValidation:
    """Tests for data quality validation rules in BronzeToSilverTransformer."""

    def test_valid_record(self):
        """A record with standard valid attributes should pass with zero errors."""
        is_valid, errors = BronzeToSilverTransformer.validate_record_quality(
            user_id="user_123",
            timestamp=datetime.now(),
            latitude=19.4326,
            longitude=-99.1332,
            humidity=45,
        )
        assert is_valid is True
        assert len(errors) == 0

    def test_latitude_out_of_bounds(self):
        """Latitude outside [-90, 90] must fail validation."""
        is_valid, errors = BronzeToSilverTransformer.validate_record_quality(
            user_id="user_123",
            timestamp=datetime.now(),
            latitude=95.5,
            longitude=-99.1332,
            humidity=50,
        )
        assert is_valid is False
        assert any("latitude" in err and "out of bounds" in err for err in errors)

    def test_longitude_out_of_bounds(self):
        """Longitude outside [-180, 180] must fail validation."""
        is_valid, errors = BronzeToSilverTransformer.validate_record_quality(
            user_id="user_123",
            timestamp=datetime.now(),
            latitude=20.0,
            longitude=195.0,
            humidity=50,
        )
        assert is_valid is False
        assert any("longitude" in err and "out of bounds" in err for err in errors)

    def test_humidity_out_of_bounds(self):
        """Humidity outside [0, 100] must fail validation."""
        is_valid, errors = BronzeToSilverTransformer.validate_record_quality(
            user_id="user_123",
            timestamp=datetime.now(),
            latitude=20.0,
            longitude=-99.0,
            humidity=120,
        )
        assert is_valid is False
        assert any("humidity" in err and "out of bounds" in err for err in errors)

    def test_missing_mandatory_fields(self):
        """Missing user_id, latitude, or longitude should fail validation."""
        is_valid, errors = BronzeToSilverTransformer.validate_record_quality(
            user_id=None,
            timestamp=None,
            latitude=None,
            longitude=None,
            humidity=None,
        )
        assert is_valid is False
        assert "user_id is missing" in errors
        assert "timestamp is missing" in errors
        assert "latitude is missing" in errors
        assert "longitude is missing" in errors


class TestSilverToGoldQueryClassification:
    """Tests for query categorization in SilverToGoldTransformer."""

    @pytest.mark.parametrize(
        "query_text,expected_category",
        [
            ("¿Cuál es el clima actual en Tokio?", "weather"),
            ("What is the current temperature and humidity?", "weather"),
            ("¿Qué hora es en Londres?", "time"),
            ("Tell me the timezone of Sydney", "time"),
            ("¿Cuál es la población de Madrid?", "demographics"),
            ("Show me demographics and language for Paris", "demographics"),
            ("¿Cuáles son los horarios pico de congestión?", "peak_hours"),
            ("Necesito recomendaciones de restaurantes", "general_query"),
            (None, "general"),
            ("", "general"),
        ],
    )
    def test_classify_query_type(self, query_text, expected_category):
        category = SilverToGoldTransformer._classify_query_type(query_text)
        assert category == expected_category
