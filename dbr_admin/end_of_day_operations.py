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
    from dbr_admin.database.db_operations import create_tables, initialize_production_db

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s  %(name)s  %(levelname)s  %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    load_dotenv()
    check_mandatory_env_vars()
    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')

    # QUOTA_MODE selects the compute-model backend ('classic' default, or
    # 'serverless' -- see databricks/serverless_quota_plan.md). The classic
    # branch below calls the same local functions this file always called
    # here -- zero behavior change. It deliberately does NOT go through
    # resource_manager.backends.classic.ClassicBackend, to avoid
    # `python -m dbr_admin.end_of_day_operations` importing this module a
    # second time under its own canonical name.
    quota_mode = os.getenv('QUOTA_MODE', 'classic').strip().lower()
    # Validated up front, before touching the DB: a typo'd QUOTA_MODE is a
    # configuration error and should fail loudly and immediately, not after
    # tables have already been created for a run that's about to abort.
    if quota_mode not in ('classic', 'serverless'):
        raise ValueError(f"Unknown QUOTA_MODE: {quota_mode!r}. Expected 'classic' or 'serverless'.")

    # Initialize the production database before creating tables
    prod_db = initialize_production_db()
    with prod_db.connection_context():
        create_tables(prod_db)
        if quota_mode == 'classic':
            restore_cluster_permissions(host, token, logger)
            log_daily_uptime(prod_db, logger)  # update the database
            send_usage_report(os.getenv('REPORT_RECIPIENT_EMAIL'), logger)
        else:  # 'serverless' -- validated above
            from .resource_manager.backends.serverless import ServerlessBackend
            backend = ServerlessBackend()
            # Mirrors the classic sequence above: restore -> roll up -> report,
            # with the report emailed exactly like send_usage_report() does
            # for classic (classic.py's backend.report() only generates the
            # HTML; the email step belongs here, at the call site).
            backend.restore(host, token, logger)
            backend.roll_up_and_reset(prod_db, logger)
            yesterday = date.today() - timedelta(days=1)
            report_html = backend.report(yesterday)
            send_emails(subject="Daily serverless usage report", body=report_html,
                        recipients=[os.getenv('REPORT_RECIPIENT_EMAIL')], logger=logger)
            backend.report(date.today() - timedelta(days=1))

    logger.info('Exiting successfully')
