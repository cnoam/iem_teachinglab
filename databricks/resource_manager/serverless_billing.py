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
"""
import logging
from datetime import date

import requests

from .dbr_host import normalize_dbr_host


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


def _submit_and_wait(host, token, warehouse_id, statement, wait_timeout="30s"):
    host = normalize_dbr_host(host)
    resp = requests.post(
        f"{host}/api/2.0/sql/statements",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"warehouse_id": warehouse_id, "statement": statement, "wait_timeout": wait_timeout},
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_billed_seconds_per_user(host: str, token: str, warehouse_id: str, usage_date: str = None) -> dict:
    """
    Returns {user_name: attached_seconds} for usage_date (local date,
    default today). Raises on any failure (permission, missing table, query
    error) -- callers must catch; see backstop_check() for the non-raising
    wrapper actually used by the backend.
    """
    usage_date = usage_date or date.today().isoformat()
    result = _submit_and_wait(host, token, warehouse_id, _billing_query(usage_date))
    status = result.get('status', {}).get('state')
    if status != 'SUCCEEDED':
        raise RuntimeError(f"system.billing.usage query did not succeed: {result.get('status')}")
    rows = (result.get('result') or {}).get('data_array') or []
    out = {}
    for run_as, seconds in rows:
        if run_as:
            out[run_as] = float(seconds or 0)
    return out


def backstop_check(host, token, warehouse_id, email_to_group, backstop_seconds,
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
        billed = fetch_billed_seconds_per_user(host, token, warehouse_id)
    except Exception as ex:
        logger.warning(f"Billing backstop check failed (skipping, non-fatal): {ex}")
        return set()

    over = set()
    for user_name, seconds in billed.items():
        group_name = email_to_group.get(user_name)
        if group_name and seconds >= backstop_seconds:
            over.add(group_name)
    return over
