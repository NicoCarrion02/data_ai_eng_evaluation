"""
ETL Step: Silver to Gold Layer Transformation.
Aggregates validated transactions from the Silver layer into analytics_metrics for dashboard consumption.
"""

import logging
from typing import Optional
import pandas as pd
from pipeline.db_connection import PipelineDB

logger = logging.getLogger("pipeline.silver_to_gold")


class SilverToGoldTransformer:
    """Aggregates enriched Silver transactions into Gold analytical metrics."""

    def __init__(self, db: PipelineDB):
        self.db = db

    @staticmethod
    def _classify_query_type(query: Optional[str]) -> str:
        """Classify query text into distinct analytical categories."""
        if not query or not isinstance(query, str):
            return "general"
        q_lower = query.lower()
        if any(k in q_lower for k in ["clima", "weather", "temperatura", "humedad", "humidity"]):
            return "weather"
        if any(k in q_lower for k in ["pico", "peak", "tránsito"]):
            return "peak_hours"
        if any(k in q_lower for k in ["hora", "time", "timezone", "zona horaria"]):
            return "time"
        if any(k in q_lower for k in ["población", "population", "demographics", "demografía"]):
            return "demographics"
        return "general_query"

    def run(self) -> int:
        """
        Execute Silver -> Gold aggregation.
        Returns the number of (date, city) aggregation rows upserted.
        """
        engine = self.db.get_engine()

        query = """
            SELECT 
                et.city,
                et.country,
                et.timestamp,
                et.temperature,
                et.weather_condition,
                ai.user_id,
                ai.user_query,
                ai.tokens_used,
                ai.response_time_ms,
                ai.sentiment,
                ai.urgency_level
            FROM enriched_transactions et
            JOIN agent_interactions ai ON et.interaction_id = ai.interaction_id
            WHERE et.is_valid = TRUE AND et.city IS NOT NULL;
        """

        try:
            df = pd.read_sql(query, con=engine)
        except Exception as e:
            logger.error(f"Failed to read from Silver/Bronze layers: {e}")
            return 0

        if df.empty:
            logger.debug("No valid Silver records to aggregate into Gold.")
            return 0

        # Feature engineering
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["metric_date"] = df["timestamp"].dt.date
        df["hour"] = df["timestamp"].dt.hour
        df["query_type"] = df["user_query"].apply(self._classify_query_type)

        logger.info(f"Aggregating {len(df)} records into Gold metrics...")
        gold_rows = []

        # Group by (metric_date, city)
        grouped = df.groupby(["metric_date", "city"])

        for (metric_date, city), group in grouped:
            country = group["country"].dropna().iloc[0] if not group["country"].dropna().empty else "Unknown"
            total_txns = len(group)
            resp_times = group["response_time_ms"].dropna()
            avg_resp = float(round(resp_times.mean(), 2)) if not resp_times.empty else 0.0
            tot_tokens = int(group["tokens_used"].fillna(0).sum())
            uniq_users = int(group["user_id"].nunique())

            # Mode calculations
            query_types = group["query_type"].dropna()
            most_common_query = query_types.mode().iloc[0] if not query_types.empty else "general_query"

            hours = group["hour"].dropna()
            peak_hour = int(hours.mode().iloc[0]) if not hours.empty else None

            temps = group["temperature"].dropna()
            avg_temp = float(round(temps.mean(), 2)) if not temps.empty else None

            weathers = group["weather_condition"].dropna()
            most_common_weather = weathers.mode().iloc[0] if not weathers.empty else None

            pos_count = int((group["sentiment"] == "positive").sum())
            neu_count = int((group["sentiment"] == "neutral").sum())
            neg_count = int((group["sentiment"] == "negative").sum())

            high_urg_count = int((group["urgency_level"] == "high").sum())
            med_urg_count = int((group["urgency_level"] == "medium").sum())
            low_urg_count = int((group["urgency_level"] == "low").sum())

            gold_rows.append({
                "metric_date": metric_date,
                "city": city,
                "country": country,
                "total_transactions": total_txns,
                "avg_response_time_ms": avg_resp,
                "total_tokens_used": tot_tokens,
                "unique_users": uniq_users,
                "most_common_query_type": most_common_query,
                "peak_hour": peak_hour,
                "avg_temperature": avg_temp,
                "most_common_weather": most_common_weather,
                "positive_sentiment_count": pos_count,
                "neutral_sentiment_count": neu_count,
                "negative_sentiment_count": neg_count,
                "high_urgency_count": high_urg_count,
                "medium_urgency_count": med_urg_count,
                "low_urgency_count": low_urg_count,
            })

        # Upsert into PostgreSQL Gold layer (analytics_metrics)
        upsert_query = """
            INSERT INTO analytics_metrics (
                metric_date,
                city,
                country,
                total_transactions,
                avg_response_time_ms,
                total_tokens_used,
                unique_users,
                most_common_query_type,
                peak_hour,
                avg_temperature,
                most_common_weather,
                positive_sentiment_count,
                neutral_sentiment_count,
                negative_sentiment_count,
                high_urgency_count,
                medium_urgency_count,
                low_urgency_count,
                aggregated_at
            ) VALUES (
                %(metric_date)s,
                %(city)s,
                %(country)s,
                %(total_transactions)s,
                %(avg_response_time_ms)s,
                %(total_tokens_used)s,
                %(unique_users)s,
                %(most_common_query_type)s,
                %(peak_hour)s,
                %(avg_temperature)s,
                %(most_common_weather)s,
                %(positive_sentiment_count)s,
                %(neutral_sentiment_count)s,
                %(negative_sentiment_count)s,
                %(high_urgency_count)s,
                %(medium_urgency_count)s,
                %(low_urgency_count)s,
                NOW()
            )
            ON CONFLICT (metric_date, city) DO UPDATE SET
                country = EXCLUDED.country,
                total_transactions = EXCLUDED.total_transactions,
                avg_response_time_ms = EXCLUDED.avg_response_time_ms,
                total_tokens_used = EXCLUDED.total_tokens_used,
                unique_users = EXCLUDED.unique_users,
                most_common_query_type = EXCLUDED.most_common_query_type,
                peak_hour = EXCLUDED.peak_hour,
                avg_temperature = EXCLUDED.avg_temperature,
                most_common_weather = EXCLUDED.most_common_weather,
                positive_sentiment_count = EXCLUDED.positive_sentiment_count,
                neutral_sentiment_count = EXCLUDED.neutral_sentiment_count,
                negative_sentiment_count = EXCLUDED.negative_sentiment_count,
                high_urgency_count = EXCLUDED.high_urgency_count,
                medium_urgency_count = EXCLUDED.medium_urgency_count,
                low_urgency_count = EXCLUDED.low_urgency_count,
                aggregated_at = NOW();
        """

        conn = self.db.get_psycopg2_connection()
        try:
            with conn.cursor() as cur:
                for row in gold_rows:
                    cur.execute(upsert_query, row)
            logger.info(f"Successfully upserted {len(gold_rows)} aggregation rows into Gold layer.")
            return len(gold_rows)
        except Exception as e:
            logger.error(f"Error persisting into Gold layer: {e}")
            return 0
        finally:
            conn.close()
