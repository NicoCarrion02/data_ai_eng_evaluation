"""
ETL Step: Bronze to Silver Layer Transformation.
Reads raw agent interactions, validates data quality, extracts location attributes,
and persists into enriched_transactions.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from pipeline.db_connection import PipelineDB

logger = logging.getLogger("pipeline.bronze_to_silver")


class BronzeToSilverTransformer:
    """Transforms raw bronze interactions into cleaned and enriched silver records."""

    def __init__(self, db: PipelineDB, batch_size: Optional[int] = None):
        self.db = db
        self.batch_size = batch_size or int(os.getenv("ETL_BATCH_SIZE", "500"))

    def process_batch(self) -> int:
        """
        Process a single batch of up to self.batch_size unprocessed Bronze records.
        Returns the number of new records successfully processed in this batch.
        """
        engine = self.db.get_engine()

        # Identify unprocessed Bronze interactions up to batch_size
        query = f"""
            SELECT 
                ai.interaction_id,
                ai.transaction_id,
                ai.user_id,
                ai.timestamp,
                ai.user_query,
                ai.agent_response,
                ai.raw_metadata
            FROM agent_interactions ai
            LEFT JOIN enriched_transactions et ON ai.interaction_id = et.interaction_id
            WHERE et.id IS NULL
            ORDER BY ai.timestamp ASC
            LIMIT {self.batch_size};
        """

        try:
            df_bronze = pd.read_sql(query, con=engine)
        except Exception as e:
            logger.error(f"Failed to read from Bronze layer: {e}")
            return 0

        if df_bronze.empty:
            logger.debug("No new Bronze records to process.")
            return 0

        logger.info(f"Processing batch of {len(df_bronze)} records from Bronze to Silver...")
        silver_records = []

        for _, row in df_bronze.iterrows():
            interaction_id = str(row["interaction_id"])
            user_id = str(row["user_id"])
            timestamp = row["timestamp"]

            raw_meta = row["raw_metadata"]
            if isinstance(raw_meta, str):
                try:
                    raw_meta = json.loads(raw_meta)
                except Exception:
                    raw_meta = {}
            elif not isinstance(raw_meta, dict):
                raw_meta = {}

            # Extract location details from MCP enriched data or original metadata
            mcp_data = raw_meta.get("mcp_enriched") or {}
            orig_meta = raw_meta.get("original_location") or {}

            city = mcp_data.get("city") or orig_meta.get("city")
            country = mcp_data.get("country")
            latitude = mcp_data.get("latitude") or orig_meta.get("latitude")
            longitude = mcp_data.get("longitude") or orig_meta.get("longitude")
            timezone = mcp_data.get("timezone")

            weather = mcp_data.get("weather") or {}
            weather_condition = weather.get("condition")
            temperature = weather.get("temperature")
            humidity = weather.get("humidity")
            wind_speed = weather.get("wind_speed")

            observations = mcp_data.get("observations") or []
            if not isinstance(observations, list):
                observations = [str(observations)]

            demographics = mcp_data.get("demographics") or {}
            population = demographics.get("population")
            language = demographics.get("language")
            currency = demographics.get("currency")

            # Data Quality Validation
            validation_errors = []
            if not user_id:
                validation_errors.append("user_id is missing")
            if pd.isna(timestamp):
                validation_errors.append("timestamp is missing")

            if latitude is not None:
                try:
                    lat_f = float(latitude)
                    if lat_f < -90 or lat_f > 90:
                        validation_errors.append(f"latitude {lat_f} out of bounds [-90, 90]")
                except (ValueError, TypeError):
                    validation_errors.append("latitude is not a valid float")
            else:
                validation_errors.append("latitude is missing")

            if longitude is not None:
                try:
                    lon_f = float(longitude)
                    if lon_f < -180 or lon_f > 180:
                        validation_errors.append(f"longitude {lon_f} out of bounds [-180, 180]")
                except (ValueError, TypeError):
                    validation_errors.append("longitude is not a valid float")
            else:
                validation_errors.append("longitude is missing")

            if humidity is not None:
                try:
                    hum_i = int(humidity)
                    if hum_i < 0 or hum_i > 100:
                        validation_errors.append(f"humidity {hum_i} out of bounds [0, 100]")
                except (ValueError, TypeError):
                    validation_errors.append("humidity is not a valid integer")

            is_valid = len(validation_errors) == 0

            silver_records.append({
                "interaction_id": interaction_id,
                "user_id": user_id,
                "timestamp": timestamp,
                "city": city,
                "country": country,
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone,
                "weather_condition": weather_condition,
                "temperature": temperature,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "observations": observations,
                "population": population,
                "language": language,
                "currency": currency,
                "is_valid": is_valid,
                "validation_errors": validation_errors,
            })

        # Insert batch into PostgreSQL Silver layer
        insert_query = """
            INSERT INTO enriched_transactions (
                interaction_id,
                user_id,
                timestamp,
                city,
                country,
                latitude,
                longitude,
                timezone,
                weather_condition,
                temperature,
                humidity,
                wind_speed,
                observations,
                population,
                language,
                currency,
                is_valid,
                validation_errors
            ) VALUES (
                %(interaction_id)s,
                %(user_id)s,
                %(timestamp)s,
                %(city)s,
                %(country)s,
                %(latitude)s,
                %(longitude)s,
                %(timezone)s,
                %(weather_condition)s,
                %(temperature)s,
                %(humidity)s,
                %(wind_speed)s,
                %(observations)s,
                %(population)s,
                %(language)s,
                %(currency)s,
                %(is_valid)s,
                %(validation_errors)s
            );
        """

        conn = self.db.get_psycopg2_connection()
        try:
            with conn.cursor() as cur:
                for rec in silver_records:
                    cur.execute(insert_query, rec)
            logger.info(f"Successfully inserted {len(silver_records)} records into Silver layer.")
            return len(silver_records)
        except Exception as e:
            logger.error(f"Error persisting records into Silver layer: {e}")
            return 0
        finally:
            conn.close()

    def run(self, max_batches: Optional[int] = None) -> int:
        """
        Execute Bronze -> Silver transformation with an immediate drain loop.
        Continuously processes batches back-to-back until all pending Bronze records
        are evacuated, preventing accumulation and snowball delays.
        
        Returns:
            The total number of records processed across all drained batches.
        """
        total_processed = 0
        batches_run = 0

        while True:
            batch_count = self.process_batch()
            total_processed += batch_count
            batches_run += 1

            # If fewer records than batch_size were returned, the queue is completely drained
            if batch_count < self.batch_size:
                break

            # Safeguard limit if specified
            if max_batches and batches_run >= max_batches:
                logger.info(f"Reached max batches limit ({max_batches}). Yielding to next step.")
                break

            logger.info(f"Drain loop: processed full batch ({batch_count} records). Immediately fetching next batch...")

        if total_processed > 0:
            logger.info(f"Drain complete: total {total_processed} records migrated to Silver in {batches_run} batch(es).")

        return total_processed
