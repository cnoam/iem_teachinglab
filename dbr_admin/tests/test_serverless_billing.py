# test_serverless_billing.py
# system.billing.usage backstop poll (plan 2.6a), in DBU per group per day. Best-effort: must
# never raise out of backstop_check(), whatever goes wrong. Against a mocked SDK client -- no
# network calls.

from datetime import date, datetime, timezone

import pytest
from unittest.mock import patch, MagicMock
from peewee import SqliteDatabase

from databricks.sdk.service.sql import StatementResponse, StatementStatus, StatementState, ResultData

from dbr_admin.resource_manager.serverless_billing import (
    backstop_check, fetch_dbu_per_user_day, dbu_per_group_day, dbu_report_html, should_run_backstop,
)
from dbr_admin.database.db_operations import IngestWatermark, GroupDailyDbu

TEST_DB = SqliteDatabase(':memory:')
MODELS = [IngestWatermark, GroupDailyDbu]
FETCH = 'dbr_admin.resource_manager.serverless_billing.fetch_dbu_per_user_day'
TODAY = date(2026, 11, 14)
YESTERDAY = date(2026, 11, 13)


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


def _response(state, data_array=None):
    return StatementResponse(
        status=StatementStatus(state=state),
        result=ResultData(data_array=data_array) if data_array is not None else None,
    )


def _utc(local_dt: datetime) -> str:
    """Local naive datetime -> the UTC string format system.billing.usage returns."""
    return local_dt.astimezone().astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def _client(rows):
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _response(
        StatementState.SUCCEEDED, data_array=rows)
    return client


# --- backstop_check(): report-only vs enforcing, recording ---

def test_backstop_check_skips_when_no_warehouse_configured():
    logger = MagicMock()
    result = backstop_check(MagicMock(), warehouse_id=None,
                            email_to_group={}, max_dbu=5.0, logger=logger)
    assert result == set()
    logger.info.assert_called_once()
    assert GroupDailyDbu.select().count() == 0


@patch(FETCH)
def test_backstop_check_flags_group_over_limit(mock_fetch):
    mock_fetch.return_value = {('a@test.com', TODAY): 7.0, ('b@test.com', TODAY): 0.5}
    result = backstop_check(MagicMock(), 'wh-id',
                            email_to_group={'a@test.com': 'group_01', 'b@test.com': 'group_02'},
                            max_dbu=5.0, logger=MagicMock(), today=TODAY)
    assert result == {'group_01'}


@patch(FETCH)
def test_backstop_check_sums_group_members(mock_fetch):
    # Two members at 3 DBU each: neither alone is over 5, the group is.
    mock_fetch.return_value = {('a@test.com', TODAY): 3.0, ('b@test.com', TODAY): 3.0}
    result = backstop_check(MagicMock(), 'wh-id',
                            email_to_group={'a@test.com': 'group_01', 'b@test.com': 'group_01'},
                            max_dbu=5.0, logger=MagicMock(), today=TODAY)
    assert result == {'group_01'}


@patch(FETCH)
def test_backstop_check_report_only_records_but_never_flags(mock_fetch):
    mock_fetch.return_value = {('a@test.com', TODAY): 999.0, ('a@test.com', YESTERDAY): 2.0,
                               ('staff@test.com', TODAY): 50.0}
    result = backstop_check(MagicMock(), 'wh-id', email_to_group={'a@test.com': 'group_01'},
                            max_dbu=None, logger=MagicMock(), today=TODAY)
    assert result == set()
    rows = {(r.group_name, r.date): r.dbu for r in GroupDailyDbu.select()}
    assert rows == {('group_01', TODAY): 999.0, ('group_01', YESTERDAY): 2.0}  # staff not recorded


@patch(FETCH)
def test_backstop_check_ignores_yesterday_for_blocking(mock_fetch):
    mock_fetch.return_value = {('a@test.com', YESTERDAY): 99.0}
    result = backstop_check(MagicMock(), 'wh-id', {'a@test.com': 'group_01'}, 5.0,
                            MagicMock(), today=TODAY)
    assert result == set()


@patch(FETCH)
def test_backstop_check_rerun_overwrites_day_total(mock_fetch):
    # Late billing rows raise the day's total on the next run; must replace, not add.
    for dbu in (1.0, 2.5):
        mock_fetch.return_value = {('a@test.com', TODAY): dbu}
        backstop_check(MagicMock(), 'wh-id', {'a@test.com': 'group_01'}, None, MagicMock(), today=TODAY)
    assert [r.dbu for r in GroupDailyDbu.select()] == [2.5]


@patch(FETCH)
def test_backstop_check_never_raises_on_failure(mock_fetch):
    mock_fetch.side_effect = RuntimeError("no access to system.billing.usage")
    logger = MagicMock()
    result = backstop_check(MagicMock(), 'wh-id', {}, 5.0, logger)
    assert result == set()
    logger.warning.assert_called_once()


# --- fetch_dbu_per_user_day(): parsing, local-day bucketing ---

def test_fetch_sums_overlapping_rows_and_buckets_by_local_day():
    # The real 2026-11-13 shape: an hourly row plus 10-minute rows inside it, two notebooks.
    rows = [
        ['a@test.com', _utc(datetime(2026, 11, 13, 16, 0)), '0.146'],
        ['a@test.com', _utc(datetime(2026, 11, 13, 16, 40)), '0.064'],
        ['a@test.com', _utc(datetime(2026, 11, 13, 17, 0)), '0.75'],
        ['a@test.com', _utc(datetime(2026, 11, 12, 23, 0)), '5.0'],   # before first_day: dropped
        ['b@test.com', _utc(datetime(2026, 11, 14, 0, 30)), None],
        [None, _utc(datetime(2026, 11, 13, 16, 0)), '9.0'],            # no run_as: dropped
    ]
    result = fetch_dbu_per_user_day(_client(rows), 'wh-id', first_day=YESTERDAY)
    assert result.keys() == {('a@test.com', YESTERDAY), ('b@test.com', TODAY)}
    assert result[('a@test.com', YESTERDAY)] == pytest.approx(0.96)
    assert result[('b@test.com', TODAY)] == 0.0


def test_fetch_reads_all_result_chunks():
    t1, t2 = _utc(datetime(2026, 11, 13, 10, 0)), _utc(datetime(2026, 11, 13, 11, 0))
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = StatementResponse(
        statement_id='st-1', status=StatementStatus(state=StatementState.SUCCEEDED),
        result=ResultData(data_array=[['a@test.com', t1, '1.0']], next_chunk_index=1))
    client.statement_execution.get_statement_result_chunk_n.return_value = ResultData(
        data_array=[['a@test.com', t2, '2.0']], next_chunk_index=None)
    assert fetch_dbu_per_user_day(client, 'wh', YESTERDAY) == {('a@test.com', YESTERDAY): 3.0}
    client.statement_execution.get_statement_result_chunk_n.assert_called_once_with('st-1', 1)


def test_fetch_raises_on_truncated_result():
    from databricks.sdk.service.sql import ResultManifest
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = StatementResponse(
        status=StatementStatus(state=StatementState.SUCCEEDED),
        manifest=ResultManifest(truncated=True), result=ResultData(data_array=[]))
    with pytest.raises(RuntimeError, match='truncated'):
        fetch_dbu_per_user_day(client, 'wh', YESTERDAY)


def test_fetch_retraction_nets_out():
    t = _utc(datetime(2026, 11, 13, 16, 0))
    rows = [['a@test.com', t, '1.0']]  # SQL already summed ORIGINAL 1.0 + RETRACTION -1.0 + RESTATEMENT 1.0
    assert fetch_dbu_per_user_day(_client(rows), 'wh', YESTERDAY) == {('a@test.com', YESTERDAY): 1.0}


def test_fetch_query_filters_dbu_and_starts_a_day_early():
    client = _client([])
    fetch_dbu_per_user_day(client, 'wh-id', first_day=YESTERDAY)
    stmt = client.statement_execution.execute_statement.call_args.kwargs['statement']
    assert "usage_date >= DATE'2026-11-12'" in stmt
    assert "usage_unit = 'DBU'" in stmt
    assert 'SUM(usage_quantity)' in stmt
    assert 'unix_timestamp' not in stmt  # the old, overcounting time sum is gone
    assert 'current_date()' not in stmt


def test_fetch_raises_on_query_failure():
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _response(StatementState.FAILED)
    with pytest.raises(RuntimeError):
        fetch_dbu_per_user_day(client, 'wh-id', YESTERDAY)


def test_dbu_per_group_day_drops_ungrouped_users():
    per_user = {('a@x', TODAY): 1.0, ('b@x', TODAY): 2.0, ('ta@x', TODAY): 4.0}
    assert dbu_per_group_day(per_user, {'a@x': 'group_01', 'b@x': 'group_01'}) == {('group_01', TODAY): 3.0}


# --- warehouse actively stopped after the query (operator request 2026-09-16) ---

def test_fetch_stops_warehouse_after_success():
    client = _client([])
    fetch_dbu_per_user_day(client, 'wh-id', YESTERDAY)
    client.warehouses.stop.assert_called_once_with('wh-id')


def test_fetch_stops_warehouse_even_on_query_failure():
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _response(StatementState.FAILED)
    with pytest.raises(RuntimeError):
        fetch_dbu_per_user_day(client, 'wh-id', YESTERDAY)
    client.warehouses.stop.assert_called_once_with('wh-id')


def test_fetch_stops_warehouse_even_if_execute_raises():
    client = MagicMock()
    client.statement_execution.execute_statement.side_effect = RuntimeError("network blip")
    with pytest.raises(RuntimeError, match="network blip"):
        fetch_dbu_per_user_day(client, 'wh-id', YESTERDAY)
    client.warehouses.stop.assert_called_once_with('wh-id')


def test_fetch_survives_stop_failure():
    # A failure to stop must not mask the real query result/error.
    client = _client([['a@test.com', _utc(datetime(2026, 11, 14, 10, 0)), '10.0']])
    client.warehouses.stop.side_effect = RuntimeError("stop failed")
    assert fetch_dbu_per_user_day(client, 'wh-id', YESTERDAY) == {('a@test.com', TODAY): 10.0}


# --- dbu_report_html(): daily-report section ---

def test_dbu_report_lists_groups_by_last_day_desc():
    GroupDailyDbu.create(group_name='group_02', date=TODAY, dbu=1.0)
    GroupDailyDbu.create(group_name='group_01', date=TODAY, dbu=12.29)
    GroupDailyDbu.create(group_name='group_01', date=YESTERDAY, dbu=2.36)
    html = dbu_report_html(TODAY)
    assert 'report only' in html
    assert html.index('group_01') < html.index('group_02')
    assert '12.29' in html and '2.36' in html and '<td style="text-align:right;">-</td>' in html


def test_dbu_report_empty_and_enforcing_wording():
    html = dbu_report_html(TODAY, max_dbu=8)
    assert 'No DBU recorded' in html and 'limit 8 DBU' in html


# --- should_run_backstop(): decoupled cadence (operator request 2026-09-16) ---

def test_should_run_backstop_true_on_first_call():
    # Realistic epoch-scale now_ms -- a real timestamp is always vastly
    # larger than any reasonable interval, so "first call" (watermark 0)
    # always looks like enough time has elapsed.
    assert should_run_backstop(interval_seconds=3600, now_ms=1_800_000_000_000) is True


def test_should_run_backstop_false_immediately_after():
    now = 1_800_000_000_000
    assert should_run_backstop(interval_seconds=3600, now_ms=now) is True
    assert should_run_backstop(interval_seconds=3600, now_ms=now + 1000) is False  # 1s later


def test_should_run_backstop_true_again_after_interval_elapses():
    now = 1_800_000_000_000
    interval_ms = 3600 * 1000
    assert should_run_backstop(interval_seconds=3600, now_ms=now) is True
    assert should_run_backstop(interval_seconds=3600, now_ms=now + interval_ms) is True


def test_should_run_backstop_advances_watermark_only_when_running():
    now = 1_800_000_000_000
    should_run_backstop(interval_seconds=3600, now_ms=now)
    wm = IngestWatermark.get(IngestWatermark.backend == 'serverless_billing_backstop')
    assert wm.last_seen_ms == now

    # A skipped call (interval not elapsed) must not move the watermark.
    should_run_backstop(interval_seconds=3600, now_ms=now + 1000)
    wm = IngestWatermark.get(IngestWatermark.backend == 'serverless_billing_backstop')
    assert wm.last_seen_ms == now


def test_should_run_backstop_tolerates_poll_start_jitter():
    # Regression (2026-11-12): last run at :30:05, next poll at +59m57s must still run,
    # otherwise the backstop slips to every 75 min. But a 15-min poll must not trigger it.
    now = 1_800_000_000_000
    assert should_run_backstop(interval_seconds=3600, now_ms=now) is True
    assert should_run_backstop(interval_seconds=3600, now_ms=now + (3600 - 3) * 1000) is True
    later = now + (3600 - 3) * 1000
    assert should_run_backstop(interval_seconds=3600, now_ms=later + 45 * 60 * 1000) is False
