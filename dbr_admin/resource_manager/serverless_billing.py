"""
system.billing.usage backstop poll (plan 2.6a), measured in DBU per group per day.

This is the only mechanism in the whole design that eventually catches a
pure-Python runaway loop (plan 1a) -- it reads what was actually billed, not
Query History execution time, but it is hours-delayed by nature. Best-effort
and non-fatal: any failure is reported to the admin and skipped, never raised --
this is a supplement to the primary quota, not a dependency of it.

**Why DBU, not minutes (2026-11-15):** the first version summed
`usage_end_time - usage_start_time` per user. Those fields are the billing
row's aggregation window (usually one hour, sometimes 10 minutes overlapping
the hourly row), not attached time. Two notebooks in the same hour, or a
10-minute row inside an hourly row, were counted twice, and an hour with
0.15 DBU of use counted as 60 minutes. That blocked group_06 on 2026-11-13
at "320 min" for 2.36 DBU of real use. DBU (usage_quantity) is what is
billed, adds up correctly across overlapping rows and notebooks, and
RETRACTION rows carry negative quantities, so a plain SUM nets corrections.

**Report-only until a limit is chosen:** SERVERLESS_BACKSTOP_MAX_DBU unset
(the default) means nothing is blocked and no student is emailed. Each run
still records DBU per group per day in GroupDailyDbu, and the daily report
shows it (dbu_report_html) so the operator can pick a limit.

Requires a SQL warehouse (SERVERLESS_BILLING_WAREHOUSE_ID); if unset, the
backstop is skipped entirely -- nothing is recorded either.

**The warehouse is actively stopped right after the query** (operator
request 2026-09-16). SAFE ONLY if SERVERLESS_BILLING_WAREHOUSE_ID points at a
warehouse dedicated to this check -- force-stopping a shared warehouse could
kill a student's concurrent session on it.

Runs on its own, slower cadence than the primary poll cycle -- see
should_run_backstop() / SERVERLESS_BACKSTOP_INTERVAL_MINUTES in
backends/serverless.py.
"""
import logging
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

from ..database.db_operations import IngestWatermark, GroupDailyDbu
from .error_report import record_run, report_error, report_ok
from .warehouse_stop import stop_warehouse as stop_dedicated_warehouse

BACKSTOP_WATERMARK_KEY = "serverless_billing_backstop"

# The poll starts every 15 min, a few seconds late each time, so "exactly 60 min since the last
# run" was often missed by seconds and the backstop slipped to 75 min (seen 2026-11-12: ~19-20
# runs/day instead of 24). Treat the interval as elapsed this much early.
CADENCE_SLACK_SECONDS = 120


def should_run_backstop(interval_seconds: float, now_ms: int = None) -> bool:
    """
    Gates the backstop check onto its own cadence, decoupled from the
    primary poll cycle. Advances the watermark and returns True when it's
    time to run; otherwise leaves it untouched and returns False.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    wm, _ = IngestWatermark.get_or_create(backend=BACKSTOP_WATERMARK_KEY, defaults={'last_seen_ms': 0})
    if now_ms - wm.last_seen_ms >= (interval_seconds - CADENCE_SLACK_SECONDS) * 1000:
        wm.last_seen_ms = now_ms
        wm.save()
        return True
    return False


def _dbu_query(since_usage_date: str) -> str:
    # Returns one row per (user, billing window start). Bucketing into *local* days is done in
    # Python (plan 2.4: local date everywhere): usage_date and the timestamps are UTC, so a
    # SQL-side date would disagree with the midnight reset near local midnight.
    # since_usage_date is a day earlier than needed, so every local day asked for is covered.
    return f"""
SELECT identity_metadata.run_as AS run_as,
       usage_start_time,
       SUM(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_date >= DATE'{since_usage_date}'
  AND usage_unit = 'DBU'
  AND product_features.is_serverless = true
  AND billing_origin_product IN ('INTERACTIVE', 'JOBS')
  AND identity_metadata.run_as IS NOT NULL
GROUP BY identity_metadata.run_as, usage_start_time
"""


def _local_date(ts: str) -> date:
    """'2026-11-13T22:00:00.000Z' (UTC) -> local date. Python 3.10's fromisoformat has no 'Z'."""
    if ts.endswith('Z'):
        ts = ts[:-1] + '+00:00'
    return datetime.fromisoformat(ts).astimezone().date()


def fetch_dbu_per_user_day(client: WorkspaceClient, warehouse_id: str, first_day: date) -> dict:
    """
    Returns {(user_name, local_date): dbu} for local days >= first_day. Raises on any failure
    (permission, missing table, query error) -- callers must catch; see backstop_check().
    """
    try:
        result = client.statement_execution.execute_statement(
            statement=_dbu_query((first_day - timedelta(days=1)).isoformat()),
            warehouse_id=warehouse_id,
            wait_timeout="30s",
        )
    finally:
        # Actively stop the warehouse now, whether the query succeeded, failed or raised (see the
        # module docstring for why this is only safe on a dedicated warehouse). Never raises.
        # stop_dedicated_warehouse() waits before stopping and re-stops if the warehouse wakes
        # back up -- see warehouse_stop.py for why.
        stop_dedicated_warehouse(client, warehouse_id,
                                 logging.getLogger('SERVERLESS_BILLING_BACKSTOP'))

    if result.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"system.billing.usage query did not succeed: {result.status}")
    if result.manifest is not None and result.manifest.truncated:
        raise RuntimeError("system.billing.usage result was truncated -- DBU totals would be too low")
    rows = list((result.result.data_array if result.result else None) or [])
    # One row per user per billing window over ~3 days can exceed one chunk; read them all
    # (silently using only the first chunk would under-count).
    next_chunk = result.result.next_chunk_index if result.result else None
    while next_chunk is not None:
        chunk = client.statement_execution.get_statement_result_chunk_n(result.statement_id, next_chunk)
        rows.extend(chunk.data_array or [])
        next_chunk = chunk.next_chunk_index
    out = defaultdict(float)
    for run_as, start_time, dbu in rows:
        if not run_as or start_time is None:
            continue
        day = _local_date(start_time)
        if day >= first_day:
            out[(run_as, day)] += float(dbu) if dbu is not None else 0.0
    return dict(out)


def dbu_per_group_day(per_user_day: dict, email_to_group: dict) -> dict:
    """{(user, day): dbu} -> {(group, day): dbu}. Users in no group (staff) are dropped."""
    out = defaultdict(float)
    for (user_name, day), dbu in per_user_day.items():
        group_name = email_to_group.get(user_name)
        if group_name:
            out[(group_name, day)] += dbu
    return dict(out)


def _record(per_group_day: dict) -> None:
    now = datetime.now()
    for (group_name, day), dbu in per_group_day.items():
        GroupDailyDbu.replace(group_name=group_name, date=day, dbu=dbu, updated_at=now).execute()


def backstop_check(client, warehouse_id, email_to_group, max_dbu,
                   logger: logging.Logger = None, today: date = None) -> set:
    """
    Records today's and yesterday's DBU per group (yesterday too, because billing rows arrive
    hours late) and returns the set of groups whose DBU today is >= max_dbu.
    max_dbu None = report-only: records, never returns a group.
    Never raises -- any failure is reported to the admin and an empty set is returned.
    """
    logger = logger or logging.getLogger('SERVERLESS_BILLING_BACKSTOP')
    today = today or date.today()
    if not warehouse_id:
        logger.info("SERVERLESS_BILLING_WAREHOUSE_ID not set -- skipping billing backstop.")
        return set()
    try:
        per_user = fetch_dbu_per_user_day(client, warehouse_id, first_day=today - timedelta(days=1))
    except Exception as ex:
        logger.warning(f"Billing backstop check failed (skipping, non-fatal): {ex}")
        # Non-fatal for the poll, but must reach the admin (throttled; never raises).
        record_run('billing_backstop', False)
        report_error('billing_backstop', 'query failed',
                     f"{ex}\n\nNobody was checked against the billing backstop this run.", logger=logger)
        return set()
    record_run('billing_backstop', True)
    report_ok('billing_backstop', 'query failed', logger=logger)

    per_group = dbu_per_group_day(per_user, email_to_group)
    _record(per_group)
    todays = {g: dbu for (g, d), dbu in per_group.items() if d == today}
    if todays:
        top = ', '.join(f"{g}={dbu:.2f}" for g, dbu in sorted(todays.items(), key=lambda x: -x[1])[:5])
        logger.info(f"Billing backstop: DBU today (top 5): {top}; limit: "
                    f"{max_dbu if max_dbu is not None else 'none (report-only)'}")
    if max_dbu is None:
        return set()
    return {g for g, dbu in todays.items() if dbu >= max_dbu}


def dbu_report_html(last_day: date, days: int = 3, max_dbu: float = None) -> str:
    """Daily-report section: DBU per group for the `days` days ending last_day (from GroupDailyDbu)."""
    day_list = [last_day - timedelta(days=i) for i in range(days - 1, -1, -1)]
    rows = list(GroupDailyDbu.select().where(GroupDailyDbu.date.between(day_list[0], last_day)))
    limit = (f"limit {max_dbu:g} DBU per group per day (enforcing)" if max_dbu is not None
             else "no limit set: report only, nobody is blocked")
    lines = [f"<h2>Serverless DBU per group (billing backstop, {limit})</h2>"]
    if not rows:
        lines.append("<p>No DBU recorded (is SERVERLESS_BILLING_WAREHOUSE_ID set?).</p>")
        return "\n".join(lines)
    table = defaultdict(dict)
    for r in rows:
        table[r.group_name][r.date] = r.dbu
    lines.append('<table border="1" style="border-collapse: collapse;">')
    lines.append('<tr><th style="text-align:left;">Group</th>'
                 + ''.join(f'<th style="text-align:right;">{d}</th>' for d in day_list) + '</tr>')
    for group_name in sorted(table, key=lambda g: -table[g].get(last_day, 0.0)):
        cells = ''.join(
            f'<td style="text-align:right;">{table[group_name][d]:.2f}</td>' if d in table[group_name]
            else '<td style="text-align:right;">-</td>' for d in day_list)
        lines.append(f'<tr><td style="text-align:left;">{group_name}</td>{cells}</tr>')
    lines.append('</table>')
    lines.append("<p>Billing data arrives hours late: the last column is likely incomplete, "
                 "and earlier days are updated only while they are today or yesterday.</p>")
    return "\n".join(lines)
