"""
ETL Pipeline Orchestrator and Periodic Runner.
Executes the Medallion Pipeline: Bronze -> Silver -> Gold.
"""

import argparse
import logging
import os
import time

from pipeline.bronze_to_silver import BronzeToSilverTransformer
from pipeline.db_connection import PipelineDB
from pipeline.silver_to_gold import SilverToGoldTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline.etl_runner")


def run_pipeline_iteration(db: PipelineDB) -> None:
    """Execute one full iteration of the medallion pipeline."""
    logger.info("--- Starting Medallion Pipeline Iteration ---")
    b2s = BronzeToSilverTransformer(db)
    s2g = SilverToGoldTransformer(db)

    # 1. Bronze -> Silver
    new_silver = b2s.run()

    # 2. Silver -> Gold (run if there are new silver records or update periodically)
    gold_upserts = s2g.run()

    logger.info(
        f"--- Pipeline Finished: Silver processed={new_silver}, Gold updated={gold_upserts} ---"
    )


def main():
    parser = argparse.ArgumentParser(description="GeoAI Analytics ETL Medallion Pipeline")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run pipeline once and exit immediately",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("ETL_INTERVAL_SECONDS", "10")),
        help="Polling interval in seconds (default: 10)",
    )
    args = parser.parse_args()

    db = PipelineDB()

    if args.once:
        logger.info("Executing single pipeline run (--once)")
        run_pipeline_iteration(db)
        return

    logger.info(f"Starting continuous ETL worker daemon (interval: {args.interval}s)...")
    while True:
        try:
            run_pipeline_iteration(db)
        except Exception as e:
            logger.error(f"Unexpected pipeline iteration error: {e}", exc_info=True)

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
