"""
Alert-only check for serverless GPU ("AI Runtime", f.k.a. Serverless GPU
Compute) usage, via system.billing.usage. Emails ADMIN_EMAIL; never blocks.

Why a separate check (not part of serverless_billing.py's backstop):
  - Confirmed live 2026-11-05: GPU rows are NOT flagged
    product_features.is_serverless -- they carry
    product_features.serverless_gpu and sku_name '*MODEL_TRAINING*', so the
    backstop query never sees them.
  - identity_metadata.run_as is NULL on GPU rows; the user is in
    identity_metadata.created_by.
  - We could not disable AI Runtime in the workspace (the `air_interactive`
    workspace setting is false but effective=true; needs account admin), so
    detection is the fallback.

Billing data is hours-delayed, so this is a "who did it yesterday/today"
alert, not real-time. A lookback window covers sessions that cross midnight
and late-arriving rows; GpuAlertSent dedupes so each
(usage_date, user, notebook) is reported once.

By default does NOT stop the warehouse it queries, so it is safe on a shared
warehouse (which then stays awake until its own auto-stop). With
GPU_ALERT_STOP_WAREHOUSE=true it stops it right after the query -- use that
only with the dedicated admin warehouse (terraform/dbr-serverless/admin_warehouse.tf).
"""
import logging
import time
from datetime import date, timedelta

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

from ..database.db_operations import GpuAlertSent
from .warehouse_stop import stop_warehouse as stop_dedicated_warehouse


def _gpu_query(workspace_id: str, since: str) -> str:
    # `since` is a Python-computed local-date literal, same reasoning as
    # serverless_billing._billing_query (avoid warehouse-session-timezone
    # current_date()).
    return f"""
SELECT u.usage_date,
       coalesce(u.identity_metadata.run_as, u.identity_metadata.created_by, 'unknown') AS user_name,
       coalesce(u.usage_metadata.notebook_id, '') AS notebook_id,
       u.sku_name,
       round(sum(u.usage_quantity), 2) AS dbu,
       round(sum(u.usage_quantity * p.pricing.effective_list.default), 2) AS usd,
       min(u.usage_start_time) AS first_seen,
       max(u.usage_end_time) AS last_seen
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND u.usage_unit = p.usage_unit
 AND u.usage_end_time >= p.price_start_time
 AND (p.price_end_time IS NULL OR u.usage_end_time < p.price_end_time)
WHERE u.workspace_id = '{workspace_id}'
  AND u.usage_date >= DATE'{since}'
  AND (u.product_features.serverless_gpu IS NOT NULL OR u.sku_name LIKE '%MODEL_TRAINING%')
GROUP BY ALL
ORDER BY u.usage_date, user_name
"""


class QueryNotReady(Exception):
    """The statement didn't finish in time (e.g. warehouse cold start). Not an error -- retry next run."""


def fetch_gpu_usage(client: WorkspaceClient, warehouse_id: str, workspace_id: str,
                    lookback_days: int, today: date = None, extra_wait_seconds: int = 50,
                    sleep=time.sleep, stop_warehouse: bool = False) -> list[dict]:
    """
    Returns one dict per (usage_date, user, notebook, sku).
    Raises QueryNotReady if the warehouse is too slow (statement is cancelled), RuntimeError on failure.
    stop_warehouse=True stops it afterwards -- ONLY for a dedicated admin warehouse
    (terraform/dbr-serverless/admin_warehouse.tf), never a shared one.
    """
    try:
        return _fetch(client, warehouse_id, workspace_id, lookback_days, today, extra_wait_seconds, sleep)
    finally:
        if stop_warehouse:
            stop_dedicated_warehouse(client, warehouse_id, logging.getLogger('GPU_ALERT'))


def _fetch(client, warehouse_id, workspace_id, lookback_days, today, extra_wait_seconds, sleep):
    today = today or date.today()
    since = (today - timedelta(days=lookback_days)).isoformat()
    result = client.statement_execution.execute_statement(
        statement=_gpu_query(workspace_id, since),
        warehouse_id=warehouse_id,
        wait_timeout="50s",
    )
    # Cold start can exceed the 50s synchronous wait: poll a bit more, then cancel.
    waited = 0
    while result.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if waited >= extra_wait_seconds:
            client.statement_execution.cancel_execution(result.statement_id)
            raise QueryNotReady(f"statement {result.statement_id} not done after ~{50 + waited}s, cancelled")
        sleep(5)
        waited += 5
        result = client.statement_execution.get_statement(result.statement_id)
    if result.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"GPU usage query did not succeed: {result.status}")
    cols = ['usage_date', 'user_name', 'notebook_id', 'sku_name', 'dbu', 'usd', 'first_seen', 'last_seen']
    rows = (result.result.data_array if result.result else None) or []
    return [dict(zip(cols, r)) for r in rows]


def _key(row: dict) -> str:
    return f"{row['usage_date']}|{row['user_name']}|{row['notebook_id']}|{row['sku_name']}"


def new_gpu_usage(rows: list[dict]) -> list[dict]:
    """Rows not alerted before. Does not mark them -- see mark_alerted()."""
    return [r for r in rows if not GpuAlertSent.select().where(GpuAlertSent.key == _key(r)).exists()]


def mark_alerted(rows: list[dict]):
    for r in rows:
        GpuAlertSent.get_or_create(key=_key(r))


def format_alert_html(rows: list[dict], host: str) -> str:
    host = host.rstrip('/')
    if not host.startswith('http'):
        host = f"https://{host}"
    lines = []
    for r in rows:
        nb = r['notebook_id']
        nb_cell = f'<a href="{host}/editor/notebooks/{nb}">{nb}</a>' if nb else '(none)'
        lines.append(
            f"<tr><td>{r['usage_date']}</td><td>{r['user_name']}</td><td>{nb_cell}</td>"
            f"<td>{r['sku_name']}</td><td>{r['dbu']}</td><td>{r['usd']}</td>"
            f"<td>{r['first_seen']} .. {r['last_seen']}</td></tr>"
        )
    return (
        "<p>Serverless <b>GPU</b> (AI Runtime) usage detected in the course workspace. "
        "Billing data is delayed by hours, so the session may already be over -- or still running.</p>"
        "<table border='1' cellpadding='4'><tr><th>date</th><th>user</th><th>notebook</th>"
        "<th>SKU</th><th>DBU</th><th>est. USD (list)</th><th>window (UTC)</th></tr>"
        + "".join(lines) + "</table>"
    )


def check_and_alert(client: WorkspaceClient, warehouse_id: str, host: str, admin_email: str,
                    lookback_days: int, send_emails, logger: logging.Logger = None,
                    stop_warehouse: bool = False) -> list[dict]:
    """
    Query, dedupe, email admin once per new row, then mark sent.
    Rows are marked only after a successful send, so a failed email is retried next run.
    Returns the rows that were alerted on.
    """
    logger = logger or logging.getLogger('GPU_ALERT')
    workspace_id = str(client.get_workspace_id())
    try:
        rows = fetch_gpu_usage(client, warehouse_id, workspace_id, lookback_days,
                               stop_warehouse=stop_warehouse)
    except QueryNotReady as ex:
        logger.warning(f"GPU check skipped this run: {ex}")
        return []
    fresh = new_gpu_usage(rows)
    if not fresh:
        logger.info(f"No new GPU usage ({len(rows)} already-reported row(s) in lookback window).")
        return []
    users = sorted({r['user_name'] for r in fresh})
    send_emails(f"ALERT: serverless GPU usage by {', '.join(users)}",
                format_alert_html(fresh, host), [admin_email], logger)
    mark_alerted(fresh)
    logger.warning(f"GPU usage alert sent for {len(fresh)} row(s): {users}")
    return fresh
