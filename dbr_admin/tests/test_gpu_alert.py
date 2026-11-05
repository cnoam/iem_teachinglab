# test_gpu_alert.py -- alert-only GPU usage check, against a mocked SDK client.

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from peewee import SqliteDatabase
from databricks.sdk.service.sql import StatementResponse, StatementStatus, StatementState, ResultData

from dbr_admin.resource_manager.gpu_alert import (
    check_and_alert, fetch_gpu_usage, _gpu_query, QueryNotReady,
)
from dbr_admin.database.db_operations import GpuAlertSent

TEST_DB = SqliteDatabase(':memory:')

ROW = ['2026-09-11', 'nagham.omar@campus.technion.ac.il', '2562372908077412',
       'PREMIUM_MODEL_TRAINING_US_EAST', '16.77', '10.9', '2026-09-11T11:20:00Z', '2026-09-11T13:40:00Z']


@pytest.fixture(autouse=True)
def db():
    GpuAlertSent.bind(TEST_DB)
    with TEST_DB.connection_context():
        TEST_DB.create_tables([GpuAlertSent])
        yield
        TEST_DB.drop_tables([GpuAlertSent])
    GpuAlertSent.bind(None)


def _client(data_array, state=StatementState.SUCCEEDED):
    c = MagicMock()
    c.get_workspace_id.return_value = 7405616428502221
    c.statement_execution.execute_statement.return_value = StatementResponse(
        status=StatementStatus(state=state), result=ResultData(data_array=data_array))
    return c


def test_query_filters_gpu_not_is_serverless():
    q = _gpu_query('123', '2026-11-01')
    assert 'serverless_gpu IS NOT NULL' in q
    assert "MODEL_TRAINING" in q
    assert "workspace_id = '123'" in q
    assert "DATE'2026-11-01'" in q and 'current_date()' not in q


def test_fetch_uses_lookback_and_never_stops_warehouse():
    c = _client([ROW])
    rows = fetch_gpu_usage(c, 'wh', '1', lookback_days=3, today=date(2026, 11, 5))
    assert rows[0]['notebook_id'] == '2562372908077412'
    assert "DATE'2026-11-02'" in c.statement_execution.execute_statement.call_args.kwargs['statement']
    c.warehouses.stop.assert_not_called()


def test_stop_warehouse_opt_in_even_on_failure():
    c = _client(None, StatementState.FAILED)
    with pytest.raises(RuntimeError):
        fetch_gpu_usage(c, 'wh', '1', 3, stop_warehouse=True)
    c.warehouses.stop.assert_called_once_with('wh')


def test_fetch_raises_on_failed_query():
    with pytest.raises(RuntimeError):
        fetch_gpu_usage(_client(None, StatementState.FAILED), 'wh', '1', 3)


def test_alerts_once_then_dedupes():
    send = MagicMock()
    c = _client([ROW])
    assert len(check_and_alert(c, 'wh', 'adb-1.azuredatabricks.net', 'admin@x', 3, send)) == 1
    send.assert_called_once()
    subject, body, recipients, _ = send.call_args.args
    assert 'nagham.omar' in subject and recipients == ['admin@x']
    assert 'https://adb-1.azuredatabricks.net/editor/notebooks/2562372908077412' in body

    send.reset_mock()
    assert check_and_alert(c, 'wh', 'adb-1.azuredatabricks.net', 'admin@x', 3, send) == []
    send.assert_not_called()


def test_failed_email_is_retried_next_run():
    send = MagicMock(side_effect=RuntimeError("smtp down"))
    c = _client([ROW])
    with pytest.raises(RuntimeError):
        check_and_alert(c, 'wh', 'h', 'admin@x', 3, send)
    assert GpuAlertSent.select().count() == 0

    send = MagicMock()
    assert len(check_and_alert(c, 'wh', 'h', 'admin@x', 3, send)) == 1


def test_slow_warehouse_polls_then_succeeds():
    c = _client([ROW])
    c.statement_execution.execute_statement.return_value = StatementResponse(
        statement_id='s1', status=StatementStatus(state=StatementState.PENDING))
    c.statement_execution.get_statement.return_value = StatementResponse(
        statement_id='s1', status=StatementStatus(state=StatementState.SUCCEEDED),
        result=ResultData(data_array=[ROW]))
    rows = fetch_gpu_usage(c, 'wh', '1', 3, sleep=lambda s: None)
    assert len(rows) == 1


def test_too_slow_warehouse_cancels_and_skips_without_email():
    c = _client([ROW])
    pending = StatementResponse(statement_id='s1', status=StatementStatus(state=StatementState.PENDING))
    c.statement_execution.execute_statement.return_value = pending
    c.statement_execution.get_statement.return_value = pending
    with pytest.raises(QueryNotReady):
        fetch_gpu_usage(c, 'wh', '1', 3, sleep=lambda s: None)
    c.statement_execution.cancel_execution.assert_called_once_with('s1')

    send = MagicMock()
    with patch('dbr_admin.resource_manager.gpu_alert.fetch_gpu_usage', side_effect=QueryNotReady('x')):
        assert check_and_alert(c, 'wh', 'h', 'admin@x', 3, send) == []
    send.assert_not_called()


def test_no_rows_no_email():
    send = MagicMock()
    assert check_and_alert(_client([]), 'wh', 'h', 'admin@x', 3, send) == []
    send.assert_not_called()
