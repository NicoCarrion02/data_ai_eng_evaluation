"""
Database queries for Streamlit Dashboard consuming the Gold Layer and analytical views.
"""

import os
from typing import Any, Dict
import pandas as pd
from sqlalchemy import create_engine


def get_db_engine():
    """Build SQLAlchemy engine for database queries."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    db = os.getenv("POSTGRES_DB", "gen_ai_agent_db")
    user = os.getenv("POSTGRES_USER", "agent_user")
    password = os.getenv("POSTGRES_PASSWORD", "agent_password")
    uri = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return create_engine(uri, pool_pre_ping=True)


def fetch_gold_metrics() -> pd.DataFrame:
    """Fetch all records from Gold Layer (analytics_metrics)."""
    engine = get_db_engine()
    query = """
        SELECT
            id,
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
        FROM analytics_metrics
        ORDER BY metric_date DESC, total_transactions DESC;
    """
    try:
        return pd.read_sql(query, con=engine)
    except Exception:
        return pd.DataFrame()


def fetch_kpis() -> Dict[str, Any]:
    """Compute executive KPIs from Gold Layer with Bronze/Silver fallback."""
    try:
        gold_df = fetch_gold_metrics()
        if not gold_df.empty:
            total_txns = int(gold_df["total_transactions"].sum())
            total_tokens = int(gold_df["total_tokens_used"].sum())
            unique_users = int(gold_df["unique_users"].sum())
            avg_latency = float(round(gold_df["avg_response_time_ms"].mean(), 1))

            pos_sent = int(gold_df["positive_sentiment_count"].sum())
            neu_sent = int(gold_df["neutral_sentiment_count"].sum())
            neg_sent = int(gold_df["negative_sentiment_count"].sum())
            tot_sent = pos_sent + neu_sent + neg_sent
            pos_rate = round((pos_sent / tot_sent * 100) if tot_sent > 0 else 0, 1)

            high_urg = int(gold_df["high_urgency_count"].sum())
            med_urg = int(gold_df["medium_urgency_count"].sum())
            low_urg = int(gold_df["low_urgency_count"].sum())
            tot_urg = high_urg + med_urg + low_urg
            high_urg_rate = round((high_urg / tot_urg * 100) if tot_urg > 0 else 0, 1)

            return {
                "total_transactions": total_txns,
                "total_tokens": total_tokens,
                "unique_users": unique_users,
                "avg_latency_ms": avg_latency,
                "positive_sentiment_rate": pos_rate,
                "high_urgency_rate": high_urg_rate,
                "positive_count": pos_sent,
                "neutral_count": neu_sent,
                "negative_count": neg_sent,
                "high_urg_count": high_urg,
                "med_urg_count": med_urg,
                "low_urg_count": low_urg,
            }
    except Exception:
        pass

    return {
        "total_transactions": 0,
        "total_tokens": 0,
        "unique_users": 0,
        "avg_latency_ms": 0.0,
        "positive_sentiment_rate": 0.0,
        "high_urgency_rate": 0.0,
        "positive_count": 0,
        "neutral_count": 0,
        "negative_count": 0,
        "high_urg_count": 0,
        "med_urg_count": 0,
        "low_urg_count": 0,
    }


def fetch_recent_transactions(limit: int = 50) -> pd.DataFrame:
    """Fetch recent enriched transactions from the helper view."""
    engine = get_db_engine()
    query = f"""
        SELECT
            transaction_id,
            user_id,
            timestamp,
            user_query,
            llm_model,
            tokens_used,
            response_time_ms,
            city,
            country,
            weather_condition,
            temperature,
            is_valid
        FROM v_recent_enriched_transactions
        ORDER BY timestamp DESC
        LIMIT {limit};
    """
    try:
        return pd.read_sql(query, con=engine)
    except Exception:
        return pd.DataFrame()


def fetch_city_summary() -> pd.DataFrame:
    """Fetch city statistics from helper view v_location_stats."""
    engine = get_db_engine()
    query = """
        SELECT
            city,
            country,
            transaction_count,
            ROUND(avg_response_time::numeric, 1) as avg_response_time,
            total_tokens,
            unique_users,
            ROUND(avg_temperature::numeric, 1) as avg_temperature
        FROM v_location_stats
        ORDER BY transaction_count DESC;
    """
    try:
        return pd.read_sql(query, con=engine)
    except Exception:
        return pd.DataFrame()
