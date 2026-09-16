# test_serverless_billing.py
# system.billing.usage backstop poll (plan 2.6a). Best-effort: must never
# raise out of backstop_check(), whatever goes wrong. Against a mocked SDK
# client -- no network calls.

import pytest
from unittest.mock import patch, MagicMock
from peewee import SqliteDatabase

from databricks.sdk.service.sql import StatementResponse, StatementStatus, StatementState, ResultData

from dbr_admin.resource_manager.serverless_billing import (
    backstop_check, fetch_billed_seconds_per_user, should_run_backstop,
)
from dbr_admin.database.db_operations import IngestWatermark

TEST_DB = SqliteDatabase(':memory:')


@pytest.fixture(scope='function', autouse=True)
def setup_teardown_db():
    IngestWatermark.bind(TEST_DB)
    with TEST_DB.connection_context():
        TEST_DB.create_tables([IngestWatermark])
        yield
        TEST_DB.drop_tables([IngestWatermark])
    IngestWatermark.bind(None)


def _response(state, data_array=None):
    return StatementResponse(
        status=StatementStatus(state=state),
        result=ResultData(data_array=data_array) if data_array is not None else None,
    )


def test_backstop_check_skips_when_no_warehouse_configured():
    logger = MagicMock()
    result = backstop_check(MagicMock(), warehouse_id=None,
                             email_to_group={}, backstop_seconds=100, logger=logger)
    assert result == set()
    logger.info.assert_called_once()


@patch('dbr_admin.resource_manager.serverless_billing.fetch_billed_seconds_per_user')
def test_backstop_check_flags_group_over_backstop(mock_fetch):
    mock_fetch.return_value = {'a@test.com': 20000.0, 'b@test.com': 10.0}
    result = backstop_check(MagicMock(), 'wh-id',
                             email_to_group={'a@test.com': 'group_01', 'b@test.com': 'group_02'},
                             backstop_seconds=18000, logger=MagicMock())
    assert result == {'group_01'}


@patch('dbr_admin.resource_manager.serverless_billing.fetch_billed_seconds_per_user')
def test_backstop_check_never_raises_on_failure(mock_fetch):
    mock_fetch.side_effect = RuntimeError("no access to system.billing.usage")
    logger = MagicMock()
    result = backstop_check(MagicMock(), 'wh-id', {}, 100, logger)
    assert result == set()
    logger.warning.assert_called_once()


def test_fetch_billed_seconds_per_user_parses_rows():
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _response(
        StatementState.SUCCEEDED, data_array=[['a@test.com', '3600.0'], ['b@test.com', None]]
    )
    result = fetch_billed_seconds_per_user(client, 'wh-id')
    assert result == {'a@test.com': 3600.0, 'b@test.com': 0.0}


def test_fetch_billed_seconds_per_user_raises_on_query_failure():
    import pytest
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _response(StatementState.FAILED)
    with pytest.raises(RuntimeError):
        fetch_billed_seconds_per_user(client, 'wh-id')


def test_fetch_billed_seconds_per_user_uses_local_date_literal():
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _response(
        StatementState.SUCCEEDED, data_array=[]
    )
    fetch_billed_seconds_per_user(client, 'wh-id', usage_date='2026-09-16')

    stmt = client.statement_execution.execute_statement.call_args.kwargs['statement']
    assert "DATE'2026-09-16'" in stmt
    assert 'current_date()' not in stmt


# --- warehouse actively stopped after the query (operator request 2026-09-16) ---

def test_fetch_billed_seconds_per_user_stops_warehouse_after_success():
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _response(
        StatementState.SUCCEEDED, data_array=[]
    )
    fetch_billed_seconds_per_user(client, 'wh-id')
    client.warehouses.stop.assert_called_once_with('wh-id')


def test_fetch_billed_seconds_per_user_stops_warehouse_even_on_query_failure():
    # Query fails (raises inside fetch_billed_seconds_per_user), but the
    # warehouse must still be stopped -- it may have started to run the
    # query before the failure.
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _response(StatementState.FAILED)
    with pytest.raises(RuntimeError):
        fetch_billed_seconds_per_user(client, 'wh-id')
    client.warehouses.stop.assert_called_once_with('wh-id')


def test_fetch_billed_seconds_per_user_stops_warehouse_even_if_execute_raises():
    client = MagicMock()
    client.statement_execution.execute_statement.side_effect = RuntimeError("network blip")
    with pytest.raises(RuntimeError, match="network blip"):
        fetch_billed_seconds_per_user(client, 'wh-id')
    client.warehouses.stop.assert_called_once_with('wh-id')


def test_fetch_billed_seconds_per_user_survives_stop_failure():
    # A failure to stop must not mask the real query result/error.
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _response(
        StatementState.SUCCEEDED, data_array=[['a@test.com', '10.0']]
    )
    client.warehouses.stop.side_effect = RuntimeError("stop failed")
    result = fetch_billed_seconds_per_user(client, 'wh-id')
    assert result == {'a@test.com': 10.0}


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
