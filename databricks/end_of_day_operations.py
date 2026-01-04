"""
Run this at the dawn of each day (e.g. at 00:05) AFTER MIDNIGHT.
Normally it is called by cron
"""

import logging
from datetime import date, timedelta

from .database.db_operations import ClusterUptime, ClusterCumulativeUptime
from .restore_cluster_permissions import restore_cluster_permissions
from .resource_manager.user_mail import send_emails
from .resource_manager.cluster_uptime import create_usage_report_daily
from .main import check_mandatory_env_vars

def send_usage_report(recipient: str, logger):
    yesterday = date.today() - timedelta(days=1)
    report_html = create_usage_report_daily(yesterday)
    send_emails(subject = f"Daily cluster usage report", body=report_html,
                recipients=[recipient], logger=logger)


def log_daily_uptime(prod_db, logger):
    """Performs daily logging and state reset atomically."""

    yesterday = date.today() - timedelta(days=1)

    with prod_db.atomic():
        # 1. LOGGING STEP: Read live data and write historical data
        clusters = list(ClusterUptime.select())
        if len(clusters) == 0:
            logger.info("No clusters found in ClusterUptime")
        for cluster in clusters:
            daily_use_sec = cluster.uptime_seconds + cluster.cumulative_seconds

            if daily_use_sec > 0:
                # Insert/Update the historical table
                ClusterCumulativeUptime.replace(
                    cluster=cluster.cluster_id,
                    date=yesterday,
                    daily_use_seconds=daily_use_sec
                ).execute()

        # 2. RESET STEP: Truncate the live table for a fresh start.
        num_deleted = ClusterUptime.delete().execute()
        logger.info(f"Purged {num_deleted} records from live table.")

    logging.info(f"Daily logging and reset for {yesterday} complete.")

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from databricks.database.db_operations import create_tables, initialize_production_db

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s  %(name)s  %(levelname)s  %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    load_dotenv()
    check_mandatory_env_vars()
    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')

    # Initialize the production database before creating tables
    prod_db = initialize_production_db()
    with prod_db.connection_context():
        create_tables(prod_db)
        restore_cluster_permissions(host, token,logger)
        log_daily_uptime(prod_db, logger) # update the database
        send_usage_report(os.getenv('REPORT_RECIPIENT_EMAIL'), logger)

    logger.info('Exiting successfully')
