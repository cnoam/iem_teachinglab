"""
Query History API ingest + aggregation for the serverless quota backend
(plan 2.2, 2.3a, 2.4).

Uses the `databricks-sdk` package (databricks.sdk.WorkspaceClient). Earlier
versions of this module used `requests` directly, because this project's
own top-level package used to be named `databricks`, shadowing the real
`databricks-sdk` package -- fixed 2026-09-16 by renaming the package to
`dbr_admin` (see serverless_quota_plan.md). Migrated to the SDK 2026-09-16.

SCOPE NOTE (first cut, operator decision): this module only ever sees
Spark/SQL execution (what the Query History API reports). A pure-Python
notebook cell issues no query and is invisible here by design -- accepted
limitation of this first cut (plan 1a), not a bug.
"""
import logging
import os
import time
from datetime import date, datetime

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import QueryFilter, TimeRange

from .serverless_quota import union_seconds
from ..database.db_operations import QueryUsage, IngestWatermark

POLL_LOOKBACK_SLACK_MS = 15 * 60 * 1000  # 15 min slack for late-arriving records (plan 2.2)
BACKEND_NAME = "serverless_query_history"
NON_TERMINAL_STATUSES = ('RUNNING', 'QUEUED')

# Safety cap on how much elapsed time a still-open (RUNNING/QUEUED) row can
# contribute, independent of the workspace's actual execution timeout
# setting (which this code has no way to read). Without this, a row that
# somehow never goes terminal -- e.g. falls outside every future poll's
# fetch window, see collect()'s window-widening below -- would otherwise
# grow its contribution at wall-clock rate forever, spuriously blocking a
# group all day over one stuck row.
STALE_ROW_CAP_SECONDS = float(os.getenv('SERVERLESS_STALE_ROW_CAP_MINUTES', 180)) * 60


def _epoch_ms_to_local_date(ms: int) -> date:
    """
    Local date bucket -- the quota-checker server's TZ is already Jerusalem
    (operator-confirmed), so datetime.fromtimestamp() gives local time
    directly, matching the classic code's implicit local-time behavior
    (date.today(), datetime.now()) and the 00:05 local cron reset. See
    plan 2.4.
    """
    return datetime.fromtimestamp(ms / 1000).date()


def fetch_query_history_rows(client: WorkspaceClient, since_ms: int) -> list:
    """
    Fetches every Query History row with query_start_time_ms >= since_ms,
    following pagination (plan 2.2: `next_page_token`). QueryHistoryAPI.list()
    is a single-page call -- the SDK does not auto-paginate this endpoint --
    so the loop below is unavoidable either way (requests or SDK).

    Returns a list of QueryInfo objects (typed: .query_id, .user_name,
    .query_start_time_ms, .duration, .status, ...).
    """
    rows = []
    page_token = None
    while True:
        page = client.query_history.list(
            filter_by=QueryFilter(query_start_time_range=TimeRange(start_time_ms=since_ms)),
            max_results=200,
            page_token=page_token,
        )
        rows.extend(page.res or [])
        if not page.has_next_page:
            break
        page_token = page.next_page_token
        if not page_token:
            break
    return rows


def ingest_rows(rows: list, email_to_group: dict) -> int:
    """
    Upserts Query History rows (QueryInfo objects) into QueryUsage, keyed by
    query_id (plan 2.2): a RUNNING row polled earlier is safely overwritten
    by its later FINISHED version, never double-counted. Rows with no
    query_id or start time are skipped (shouldn't happen per the API, but
    ingest must not crash on a malformed record).

    `duration` is intentionally stored as the API gives it -- null for
    RUNNING/QUEUED rows (confirmed live, plan 2.2). Elapsed time for a
    still-running row is computed at read time by
    group_usage_seconds_for_day(), never baked in here.
    """
    written = 0
    for row in rows:
        query_id = row.query_id
        start_ms = row.query_start_time_ms
        if not query_id or start_ms is None:
            continue
        user_name = row.user_name or row.executed_as_user_name or ''
        status = row.status.value if row.status is not None else 'UNKNOWN'
        QueryUsage.replace(
            query_id=query_id,
            user_name=user_name,
            group_name=email_to_group.get(user_name),
            day=_epoch_ms_to_local_date(start_ms),
            start_time_ms=start_ms,
            duration_ms=row.duration,
            status=status,
        ).execute()
        written += 1
    return written


def _earliest_open_row_start_ms_today():
    """
    Earliest start_time_ms among today's still-non-terminal QueryUsage rows,
    or None if there are none. Used to widen the fetch window (see collect())
    so a long-running query keeps getting refreshed on every poll until it
    goes terminal, instead of aging out of the normal watermark-based window
    and freezing at whatever duration it last had (plan 2.2 bug, fixed here).
    """
    from peewee import fn
    return (QueryUsage
            .select(fn.MIN(QueryUsage.start_time_ms))
            .where((QueryUsage.status.in_(NON_TERMINAL_STATUSES)) & (QueryUsage.day == date.today()))
            .scalar())


def collect(client: WorkspaceClient, email_to_group: dict, logger: logging.Logger = None) -> int:
    """
    One ingest cycle: read the watermark, fetch rows since
    watermark - slack (widened to also cover any row still open from an
    earlier poll today, so it keeps getting refreshed until it goes
    terminal -- see _earliest_open_row_start_ms_today()), upsert them,
    advance the watermark to now. Returns the number of rows ingested.
    """
    logger = logger or logging.getLogger('SERVERLESS_INGEST')
    now_ms = int(time.time() * 1000)

    watermark, _ = IngestWatermark.get_or_create(backend=BACKEND_NAME, defaults={'last_seen_ms': 0})
    since_ms = max(0, watermark.last_seen_ms - POLL_LOOKBACK_SLACK_MS)

    earliest_open_ms = _earliest_open_row_start_ms_today()
    if earliest_open_ms is not None:
        since_ms = min(since_ms, earliest_open_ms)
    # Clamp to start of today (local) -- a row that's permanently stuck
    # non-terminal (rather than merely long-running) still can't push the
    # window back indefinitely and re-fetch unbounded history every poll.
    start_of_today_ms = int(datetime.combine(date.today(), datetime.min.time()).timestamp() * 1000)
    since_ms = max(since_ms, start_of_today_ms)

    rows = fetch_query_history_rows(client, since_ms)
    written = ingest_rows(rows, email_to_group)

    watermark.last_seen_ms = now_ms
    watermark.save()

    logger.info(f"Serverless ingest: {written} rows (since {since_ms}ms, watermark now {now_ms}ms)")
    return written


def group_usage_seconds_for_day(group_name: str, day, now_ms: int = None) -> float:
    """
    Reads all QueryUsage rows for (group_name, day) and returns the
    union-of-intervals total (plan 2.3a), computed fresh from raw rows on
    every call -- never a stored accumulated total, since a still-running
    row's effective end keeps moving between polls (plan 2.3a).
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    intervals = []
    for row in QueryUsage.select().where(
        (QueryUsage.group_name == group_name) & (QueryUsage.day == day)
    ):
        start_s = row.start_time_ms / 1000.0
        if row.duration_ms is not None:
            end_s = start_s + row.duration_ms / 1000.0
        else:
            # Still RUNNING/QUEUED -- elapsed so far (plan 2.2), capped so a
            # row that never goes terminal can't inflate usage without
            # bound (see STALE_ROW_CAP_SECONDS).
            end_s = min(now_ms / 1000.0, start_s + STALE_ROW_CAP_SECONDS)
        intervals.append((start_s, end_s))
    return union_seconds(intervals)
