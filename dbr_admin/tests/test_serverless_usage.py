# test_serverless_usage.py
# Query History ingest + read-time aggregation (plan 2.2, 2.3a).

import time
import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from peewee import SqliteDatabase

from dbr_admin.resource_manager.serverless_usage import (
    ingest_rows, collect, group_usage_seconds_for_day, _epoch_ms_to_local_date,
    fetch_query_history_rows,
)
from dbr_admin.database.db_operations import QueryUsage, IngestWatermark

TEST_DB = SqliteDatabase(':memory:')
MODELS = [QueryUsage, IngestWatermark]


@pytest.fixture(scope='function', autouse=True)
def setup_teardown_db():
    for m in MODELS:
        m.bind(TEST_DB)
    with TEST_DB.connection_context():
        TEST_DB.create_tables(MODELS)
        yield
        TEST_DB.drop_tables(MODELS)
    for m in MODELS:
        m.bind(None)


# --- ingest_rows(): the upsert-by-query_id contract ---

def test_ingest_rows_writes_running_row_with_null_duration():
    # Real API shape observed live: no 'duration' key at all while RUNNING.
    rows = [{
        'query_id': 'q1', 'user_name': 'a@test.com',
        'query_start_time_ms': 1_789_544_737_861, 'status': 'RUNNING',
    }]
    written = ingest_rows(rows, email_to_group={'a@test.com': 'group_01'})

    assert written == 1
    row = QueryUsage.get(QueryUsage.query_id == 'q1')
    assert row.status == 'RUNNING'
    assert row.duration_ms is None
    assert row.group_name == 'group_01'


def test_ingest_rows_upserts_running_to_finished_no_duplicate():
    running = [{'query_id': 'q1', 'user_name': 'a@test.com',
                'query_start_time_ms': 1_000_000, 'status': 'RUNNING'}]
    finished = [{'query_id': 'q1', 'user_name': 'a@test.com',
                 'query_start_time_ms': 1_000_000, 'status': 'FINISHED', 'duration': 47903}]

    ingest_rows(running, {})
    ingest_rows(finished, {})

    assert QueryUsage.select().count() == 1
    row = QueryUsage.get(QueryUsage.query_id == 'q1')
    assert row.status == 'FINISHED'
    assert row.duration_ms == 47903


def test_ingest_rows_skips_malformed_records():
    rows = [
        {'user_name': 'a@test.com', 'query_start_time_ms': 1, 'status': 'FINISHED'},  # no query_id
        {'query_id': 'q2', 'user_name': 'a@test.com', 'status': 'FINISHED'},  # no start time
        {'query_id': 'q3', 'user_name': 'a@test.com', 'query_start_time_ms': 1, 'status': 'FINISHED'},
    ]
    written = ingest_rows(rows, {})
    assert written == 1
    assert QueryUsage.select().count() == 1


def test_ingest_rows_ungrouped_user_gets_null_group():
    rows = [{'query_id': 'q1', 'user_name': 'staff@test.com',
             'query_start_time_ms': 1, 'status': 'FINISHED', 'duration': 500}]
    ingest_rows(rows, email_to_group={})  # staff@test.com not in the map
    row = QueryUsage.get(QueryUsage.query_id == 'q1')
    assert row.group_name is None


# --- collect(): watermark handling, via a mocked fetch ---

@patch('dbr_admin.resource_manager.serverless_usage.fetch_query_history_rows')
def test_collect_advances_watermark_and_ingests(mock_fetch):
    mock_fetch.return_value = [
        {'query_id': 'q1', 'user_name': 'a@test.com', 'query_start_time_ms': 1, 'status': 'FINISHED', 'duration': 10},
    ]
    written = collect('host', 'token', {'a@test.com': 'group_01'}, logger=MagicMock())

    assert written == 1
    wm = IngestWatermark.get(IngestWatermark.backend == 'serverless_query_history')
    assert wm.last_seen_ms > 0


@patch('dbr_admin.resource_manager.serverless_usage.fetch_query_history_rows')
def test_collect_uses_watermark_minus_slack_as_since(mock_fetch):
    # Watermark set realistically close to "now" (an hour ago) so the
    # start-of-today clamp (see test below) doesn't dominate the result --
    # this test is specifically about the slack subtraction.
    mock_fetch.return_value = []
    watermark_ms = int(time.time() * 1000) - 60 * 60 * 1000  # 1h ago
    IngestWatermark.create(backend='serverless_query_history', last_seen_ms=watermark_ms)

    collect('host', 'token', {}, logger=MagicMock())

    called_since = mock_fetch.call_args.args[2]
    assert called_since == watermark_ms - 15 * 60 * 1000  # POLL_LOOKBACK_SLACK_MS


@patch('dbr_admin.resource_manager.serverless_usage.fetch_query_history_rows')
def test_collect_clamps_since_to_start_of_today(mock_fetch):
    # A stale watermark (e.g. left over from a much earlier run) must not
    # cause collect() to re-fetch unbounded history -- it's clamped to the
    # start of today (local).
    mock_fetch.return_value = []
    IngestWatermark.create(backend='serverless_query_history', last_seen_ms=1_000_000_000)  # 1970

    collect('host', 'token', {}, logger=MagicMock())

    called_since = mock_fetch.call_args.args[2]
    start_of_today_ms = int(datetime.combine(date.today(), datetime.min.time()).timestamp() * 1000)
    assert called_since == start_of_today_ms


@patch('dbr_admin.resource_manager.serverless_usage.fetch_query_history_rows')
def test_collect_widens_window_for_an_open_row_from_earlier_today(mock_fetch):
    # The bug this guards against: a query still RUNNING from before
    # watermark - slack must keep being re-fetched every poll until it goes
    # terminal, or its usage contribution silently freezes.
    mock_fetch.return_value = []
    now_ms = int(time.time() * 1000)
    open_row_start_ms = now_ms - 60 * 60 * 1000  # started 1h ago, still open
    QueryUsage.create(query_id='still-open', user_name='a@test.com', group_name='group_01',
                       day=date.today(), start_time_ms=open_row_start_ms, duration_ms=None,
                       status='RUNNING')
    # Watermark is recent -- without the widening fix, since_ms would be
    # much later than open_row_start_ms and the open row would be missed.
    IngestWatermark.create(backend='serverless_query_history', last_seen_ms=now_ms - 60_000)

    collect('host', 'token', {}, logger=MagicMock())

    called_since = mock_fetch.call_args.args[2]
    assert called_since <= open_row_start_ms


# --- group_usage_seconds_for_day(): union computed at read time ---

def test_group_usage_seconds_for_day_finished_rows():
    QueryUsage.create(query_id='q1', user_name='a@test.com', group_name='group_01',
                       day=date(2026, 9, 16), start_time_ms=0, duration_ms=120_000, status='FINISHED')
    QueryUsage.create(query_id='q2', user_name='b@test.com', group_name='group_01',
                       day=date(2026, 9, 16), start_time_ms=200_000, duration_ms=60_000, status='FINISHED')

    total = group_usage_seconds_for_day('group_01', date(2026, 9, 16))
    assert total == 180.0  # 120s + 60s, non-overlapping


def test_group_usage_seconds_for_day_running_row_uses_now():
    start_ms = 1_000_000
    now_ms = start_ms + 90_000  # 90s elapsed
    QueryUsage.create(query_id='q1', user_name='a@test.com', group_name='group_01',
                       day=date(2026, 9, 16), start_time_ms=start_ms, duration_ms=None, status='RUNNING')

    total = group_usage_seconds_for_day('group_01', date(2026, 9, 16), now_ms=now_ms)
    assert total == 90.0


def test_group_usage_seconds_for_day_ignores_other_groups_and_days():
    QueryUsage.create(query_id='q1', user_name='a@test.com', group_name='group_02',
                       day=date(2026, 9, 16), start_time_ms=0, duration_ms=999_000, status='FINISHED')
    QueryUsage.create(query_id='q2', user_name='a@test.com', group_name='group_01',
                       day=date(2026, 9, 15), start_time_ms=0, duration_ms=999_000, status='FINISHED')

    total = group_usage_seconds_for_day('group_01', date(2026, 9, 16))
    assert total == 0.0


# --- local date bucketing ---

def test_epoch_ms_to_local_date():
    # A concrete instant, just confirming it doesn't crash and returns a date
    # (the actual UTC offset depends on the running machine's TZ -- see plan
    # 2.4 for why local time, not UTC, is used here).
    d = _epoch_ms_to_local_date(1_789_544_737_861)
    assert isinstance(d, date)
