"""
Daily-report section: users who opened many Databricks Connect (Spark Connect) sessions.

Why (postmortem 2026-11-18): two students ran scripts from their laptops through Databricks
Connect -- one of them driven by an AI coding agent -- and every new Python process opened a
new serverless session. 61 sessions with 15 min of query time cost 44 DBU; 11 sessions cost
33 DBU in 80 min. The primary quota counts query time, so it barely saw this; billing does.
This section names the pattern the day after, so the admin can talk to the group.

Source: system.query.history (client_application = 'SPARK_CONNECT', one session_id per
session). Runs on the dedicated admin warehouse (SERVERLESS_BILLING_WAREHOUSE_ID, stopped
afterwards); if unset, the section says so. Never raises -- a failure is emailed to the admin
via error_report and shown in the section.
"""
import logging
import os
import time
from datetime import date, datetime, time as dtime, timedelta
from html import escape

from databricks.sdk.service.sql import StatementState

from .error_report import record_run, report_error, report_ok
from .warehouse_stop import stop_warehouse

JOB = 'spark_connect_report'
DEFAULT_MIN_SESSIONS = 10
QUERY_TIMEOUT_SECONDS = 180  # cold start of the admin warehouse included; end_of_day has 600s
_sleep = time.sleep


def _day_bounds_ms(day: date) -> tuple:
    """Local midnight to midnight, as epoch ms (timezone-free in SQL via timestamp_millis)."""
    start = datetime.combine(day, dtime.min).astimezone()
    end = datetime.combine(day + timedelta(days=1), dtime.min).astimezone()
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _query(day: date, min_sessions: int) -> str:
    start_ms, end_ms = _day_bounds_ms(day)
    return f"""
SELECT executed_by,
       count(DISTINCT session_id) AS sessions,
       count(*) AS queries,
       round(sum(total_duration_ms) / 60000, 1) AS query_minutes
FROM system.query.history
WHERE start_time >= timestamp_millis({start_ms}) AND start_time < timestamp_millis({end_ms})
  AND client_application = 'SPARK_CONNECT'
GROUP BY executed_by
HAVING count(DISTINCT session_id) >= {int(min_sessions)}
ORDER BY sessions DESC
"""


def _run(client, warehouse_id: str, sql: str) -> list:
    """Execute and wait (polling) up to QUERY_TIMEOUT_SECONDS. Raises on failure or timeout."""
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
    r = client.statement_execution.execute_statement(statement=sql, warehouse_id=warehouse_id,
                                                     wait_timeout="30s")
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.monotonic() > deadline:
            try:
                client.statement_execution.cancel_execution(r.statement_id)
            except Exception:
                pass
            raise RuntimeError(f"system.query.history query still {r.status.state} "
                               f"after {QUERY_TIMEOUT_SECONDS}s")
        _sleep(5)
        r = client.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"system.query.history query did not succeed: {r.status}")
    rows = list((r.result.data_array if r.result else None) or [])
    next_chunk = r.result.next_chunk_index if r.result else None
    while next_chunk is not None:
        chunk = client.statement_execution.get_statement_result_chunk_n(r.statement_id, next_chunk)
        rows.extend(chunk.data_array or [])
        next_chunk = chunk.next_chunk_index
    return rows


def fetch_heavy_spark_connect_users(client, warehouse_id: str, day: date, min_sessions: int) -> list:
    """[(user, sessions, queries, query_minutes)] for users with >= min_sessions sessions on `day`."""
    try:
        rows = _run(client, warehouse_id, _query(day, min_sessions))
    finally:
        stop_warehouse(client, warehouse_id, logging.getLogger(JOB))
    return [(u, int(s), int(n), float(m or 0)) for u, s, n, m in rows if u]


def spark_connect_report_html(day: date, client=None, email_to_group: dict = None,
                              logger: logging.Logger = None) -> str:
    """The daily-report section for `day`. Never raises."""
    logger = logger or logging.getLogger(JOB)
    min_sessions = int(os.getenv('SPARK_CONNECT_MIN_SESSIONS', DEFAULT_MIN_SESSIONS))
    title = f"<h2>Databricks Connect: users with {min_sessions}+ sessions, {day}</h2>"
    warehouse_id = os.getenv('SERVERLESS_BILLING_WAREHOUSE_ID')
    if not warehouse_id:
        return title + "<p>Skipped: SERVERLESS_BILLING_WAREHOUSE_ID not set.</p>"
    try:
        if client is None or email_to_group is None:
            from databricks.sdk import WorkspaceClient
            from ..DataBricksGroups import DataBricksGroups
            from .dbr_host import normalize_dbr_host
            from .group_map import build_email_to_group_map
            host = normalize_dbr_host(os.getenv('DATABRICKS_HOST'))
            token = os.getenv('DATABRICKS_TOKEN')
            client = client or WorkspaceClient(host=host, token=token)
            if email_to_group is None:
                email_to_group = build_email_to_group_map(DataBricksGroups(host=host, token=token), logger)
        users = fetch_heavy_spark_connect_users(client, warehouse_id, day, min_sessions)
    except Exception as ex:
        logger.warning(f"Spark Connect report failed: {ex}")
        record_run(JOB, False)
        report_error(JOB, 'query failed', str(ex), logger=logger)
        return title + f"<p style='color:red'>Check failed: {escape(str(ex))}</p>"
    record_run(JOB, True)
    report_ok(JOB, 'query failed', logger=logger)

    if not users:
        return title + "<p>None.</p>"
    rows = "".join(
        f"<tr><td>{escape(email_to_group.get(u, '-'))}</td><td>{escape(u)}</td>"
        f"<td style='text-align:right'>{s}</td><td style='text-align:right'>{n}</td>"
        f"<td style='text-align:right'>{m:.1f}</td></tr>" for u, s, n, m in users)
    return (title +
            "<p>Each session is a separately billed serverless compute session, so many short "
            "sessions cost far more than their query time (usually a script or AI agent starting "
            "a new Python process per command). Compare with the DBU table above.</p>"
            "<table border='1' style='border-collapse: collapse;'><tr><th>Group</th><th>User</th>"
            "<th>Sessions</th><th>Queries</th><th>Query min</th></tr>" + rows + "</table>")
