"""
system.billing.usage backstop poll (plan 2.6a).

This is the only mechanism in the whole design that eventually catches a
pure-Python runaway loop (plan 1a) -- it reads true billed attached-session
time (system.billing.usage), not Query History execution time, but it is
hours-delayed by nature. Best-effort and non-fatal: any failure (no access
to the system table, no warehouse configured) is logged and skipped, never
raised -- this is a supplement to the primary quota, not a dependency of it
(plan 2.6a: "Skip both silently... if the account lacks read access").

Requires a SQL warehouse to run the query against (system tables aren't
queryable from the Statement Execution API without one) -- set
SERVERLESS_BILLING_WAREHOUSE_ID. If unset, this backstop is skipped
entirely; the primary Query History-based quota (serverless_usage.py) is
unaffected either way.

**The warehouse is actively stopped right after the query** (not left to
its own auto_stop_mins idle timeout) -- operator request 2026-09-16.
SAFE ONLY if SERVERLESS_BILLING_WAREHOUSE_ID points at a warehouse
dedicated to this check. Do NOT point it at a warehouse shared with
students (confirmed live: both known warehouses in this workspace grant
CAN_USE to either `all_student_groups` or the built-in `users` group,
i.e. every workspace user) -- force-stopping a shared warehouse the
moment this query finishes could kill a student's unrelated, concurrent
session on the same warehouse.

Runs on its own, slower cadence than the primary poll cycle -- see
should_run_backstop() / SERVERLESS_BACKSTOP_INTERVAL_MINUTES in
backends/serverless.py (operator request 2026-09-16: was previously
running every 15-minute poll, cold-starting the billing warehouse each
time it did).

Uses the `databricks-sdk` package (databricks.sdk.WorkspaceClient) --
migrated 2026-09-16 from `requests` (see serverless_enforcement.py's
docstring for why the requests version existed in the first place).
"""
import logging
import time
from datetime import date

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

from ..database.db_operations import IngestWatermark

BACKSTOP_WATERMARK_KEY = "serverless_billing_backstop"


def should_run_backstop(interval_seconds: float, now_ms: int = None) -> bool:
    """
    Gates the backstop check onto its own cadence, decoupled from the
    primary poll cycle. Advances the watermark and returns True when it's
    time to run; otherwise leaves it untouched and returns False.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    wm, _ = IngestWatermark.get_or_create(backend=BACKSTOP_WATERMARK_KEY, defaults={'last_seen_ms': 0})
    if now_ms - wm.last_seen_ms >= interval_seconds * 1000:
        wm.last_seen_ms = now_ms
        wm.save()
        return True
    return False


def _billing_query(usage_date: str) -> str:
    # usage_date is a Python-computed literal (local date, matching
    # plan 2.4's "local date, not UTC" decision everywhere else in this
    # system) rather than SQL's current_date(), which would evaluate in the
    # warehouse session's timezone (spark.sql.session.timeZone, default
    # Etc/UTC) and silently disagree with the rest of this system near
    # local midnight.
    return f"""
SELECT identity_metadata.run_as AS run_as,
       SUM(unix_timestamp(usage_end_time) - unix_timestamp(usage_start_time)) AS attached_seconds
FROM system.billing.usage
WHERE usage_date = DATE'{usage_date}'
  AND product_features.is_serverless = true
  AND billing_origin_product IN ('INTERACTIVE', 'JOBS')
GROUP BY identity_metadata.run_as
"""


def fetch_billed_seconds_per_user(client: WorkspaceClient, warehouse_id: str,
                                   usage_date: str = None) -> dict:
    """
    Returns {user_name: attached_seconds} for usage_date (local date,
    default today). Raises on any failure (permission, missing table, query
    error) -- callers must catch; see backstop_check() for the non-raising
    wrapper actually used by the backend.
    """
    usage_date = usage_date or date.today().isoformat()
    try:
        result = client.statement_execution.execute_statement(
            statement=_billing_query(usage_date),
            warehouse_id=warehouse_id,
            wait_timeout="30s",
        )
    finally:
        # Actively stop the warehouse now, rather than waiting for its
        # auto_stop_mins idle timeout -- see this module's docstring for
        # why this is only safe against a dedicated warehouse. Runs
        # whether the query succeeded, failed, or raised; a failure to
        # stop is logged, never raised (the query result/error is what
        # actually matters to the caller).
        try:
            client.warehouses.stop(warehouse_id)
        except Exception as stop_ex:
            logging.getLogger('SERVERLESS_BILLING_BACKSTOP').warning(
                f"Could not stop warehouse {warehouse_id} after billing query: {stop_ex}"
            )

    if result.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"system.billing.usage query did not succeed: {result.status}")
    rows = (result.result.data_array if result.result else None) or []
    out = {}
    for run_as, seconds in rows:
        if run_as:
            out[run_as] = float(seconds) if seconds is not None else 0.0
    return out


def backstop_check(client, warehouse_id, email_to_group, backstop_seconds,
                    logger: logging.Logger = None) -> set:
    """
    Returns the set of group_names whose billed attached time today meets
    or exceeds backstop_seconds. Never raises -- any failure is logged and
    an empty set is returned, per plan 2.6a's "best-effort, not blocking".
    """
    logger = logger or logging.getLogger('SERVERLESS_BILLING_BACKSTOP')
    if not warehouse_id:
        logger.info("SERVERLESS_BILLING_WAREHOUSE_ID not set -- skipping billing backstop.")
        return set()
    try:
        billed = fetch_billed_seconds_per_user(client, warehouse_id)
    except Exception as ex:
        logger.warning(f"Billing backstop check failed (skipping, non-fatal): {ex}")
        return set()

    over = set()
    for user_name, seconds in billed.items():
        group_name = email_to_group.get(user_name)
        if group_name and seconds >= backstop_seconds:
            over.add(group_name)
    return over
