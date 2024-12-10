"""
Run this at the end of every day (e.g. at 23:55).
Normally it is called by cron
"""

import logging
from restore_cluster_permissions import restore_cluster_permissions
from resource_manager.user_mail import send_emails
from resource_manager.cluster_uptime import create_usage_report

def send_usage_report(logger):
    report_html = create_usage_report()
    send_emails(f"Daily cluster usage report", body=report_html,
                recipients=['cnoam@technion.ac.il'], logger=logger)


if __name__ == "__main__":
    import os

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s  %(name)s  %(levelname)s  %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    from dotenv import load_dotenv
    load_dotenv()
    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')

    restore_cluster_permissions(host, token,logger)
    send_usage_report(logger)

    logger.info('Exiting successfully')