"""
Cron entry point: email ADMIN_EMAIL when serverless GPU (AI Runtime) usage
appears in system.billing.usage. Alert only -- never blocks anyone.
See resource_manager/gpu_alert.py for details.

    python -m dbr_admin.gpu_alert

Env vars (from .env):
  DATABRICKS_HOST, DATABRICKS_TOKEN, AZURE_EMAIL_ACCESS_KEY, ADMIN_EMAIL  (required)
  GPU_ALERT_WAREHOUSE_ID   SQL warehouse to run the query on (required). Stopped afterwards only if GPU_ALERT_STOP_WAREHOUSE=true.
  GPU_ALERT_LOOKBACK_DAYS  default 3 (billing rows arrive hours late)
  GPU_ALERT_STOP_WAREHOUSE 'true' to stop the warehouse after the query -- dedicated admin warehouse only
"""
import logging
import os
import traceback

from databricks.sdk import WorkspaceClient


REQUIRED_ENV = ('DATABRICKS_HOST', 'DATABRICKS_TOKEN', 'AZURE_EMAIL_ACCESS_KEY', 'ADMIN_EMAIL',
                'GPU_ALERT_WAREHOUSE_ID')


def main():
    from .database.db_operations import create_tables, initialize_production_db
    from .resource_manager.dbr_host import normalize_dbr_host
    from .resource_manager.gpu_alert import check_and_alert
    from .resource_manager.user_mail import send_emails

    warehouse_id = os.getenv('GPU_ALERT_WAREHOUSE_ID')
    host = normalize_dbr_host(os.getenv('DATABRICKS_HOST'))
    client = WorkspaceClient(host=host, token=os.getenv('DATABRICKS_TOKEN'))

    prod_db = initialize_production_db()
    with prod_db.connection_context():
        create_tables(prod_db)
        check_and_alert(client, warehouse_id, host, os.getenv('ADMIN_EMAIL'),
                        int(os.getenv('GPU_ALERT_LOOKBACK_DAYS', 3)), send_emails,
                        stop_warehouse=os.getenv('GPU_ALERT_STOP_WAREHOUSE', '').strip().lower() == 'true')


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    # Config errors fail loudly (non-zero exit, no email) -- same rule as poll_clusters.py.
    missing = [v for v in REQUIRED_ENV if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"missing environment variables: {missing}")
    try:
        main()
    except Exception as ex:
        from .resource_manager.user_mail import send_emails
        logging.error(f"GPU alert check crashed: {ex}")
        send_emails("GPU alert check crashed!", f"<pre>{ex}\n\n{traceback.format_exc()}</pre>",
                    [os.getenv('ADMIN_EMAIL')], None)
        raise
