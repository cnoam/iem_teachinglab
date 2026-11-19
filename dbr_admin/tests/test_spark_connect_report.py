# test_spark_connect_report.py -- daily "many Databricks Connect sessions" section (postmortem
# 2026-11-18). Mocked SDK client, no network calls.
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase
from databricks.sdk.service.sql import StatementResponse, StatementStatus, StatementState, ResultData

from dbr_admin.database.db_operations import ErrorReport, JobRunCount
from dbr_admin.resource_manager import spark_connect_report as scr
from dbr_admin.resource_manager import error_report as er

TEST_DB = SqliteDatabase(':memory:')
DAY = date(2026, 11, 18)


@pytest.fixture(autouse=True)
def db(monkeypatch):
    for m in (ErrorReport, JobRunCount):
        m.bind(TEST_DB)
    monkeypatch.setattr(scr, '_sleep', lambda s: None)
    monkeypatch.setenv('SERVERLESS_BILLING_WAREHOUSE_ID', 'wh')
    monkeypatch.delenv('SPARK_CONNECT_MIN_SESSIONS', raising=False)
    with TEST_DB.connection_context():
        TEST_DB.create_tables([ErrorReport, JobRunCount])
        yield
        TEST_DB.drop_tables([ErrorReport, JobRunCount])


def _resp(state, rows=None, sid='st'):
    return StatementResponse(statement_id=sid, status=StatementStatus(state=state),
                             result=ResultData(data_array=rows) if rows is not None else None)


def test_lists_heavy_users_with_group():
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _resp(
        StatementState.SUCCEEDED, [['a@x', '61', '445', '15.4'], ['b@x', '11', '284', '21.2']])
    html = scr.spark_connect_report_html(DAY, client=client, email_to_group={'a@x': 'group_21'})
    assert 'group_21' in html and '61' in html and 'b@x' in html
    assert html.index('a@x') < html.index('b@x')
    client.warehouses.stop.assert_called()
    assert JobRunCount.get(JobRunCount.job == 'spark_connect_report').ok == 1


def test_query_uses_local_day_epoch_bounds_and_threshold(monkeypatch):
    monkeypatch.setenv('SPARK_CONNECT_MIN_SESSIONS', '7')
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _resp(StatementState.SUCCEEDED, [])
    html = scr.spark_connect_report_html(DAY, client=client, email_to_group={})
    sql = client.statement_execution.execute_statement.call_args.kwargs['statement']
    start_ms = int(datetime(2026, 11, 18).astimezone().timestamp() * 1000)
    assert f"timestamp_millis({start_ms})" in sql
    assert "client_application = 'SPARK_CONNECT'" in sql and '>= 7' in sql
    assert 'None.' in html and '7+ sessions' in html


def test_polls_until_done():
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _resp(StatementState.PENDING)
    client.statement_execution.get_statement.side_effect = [
        _resp(StatementState.RUNNING), _resp(StatementState.SUCCEEDED, [['a@x', '12', '30', '1.0']])]
    html = scr.spark_connect_report_html(DAY, client=client, email_to_group={})
    assert 'a@x' in html


def test_timeout_is_reported_and_never_raises(monkeypatch):
    sent = MagicMock()
    monkeypatch.setattr(er, '_default_send', lambda: sent)
    monkeypatch.setattr(scr, 'QUERY_TIMEOUT_SECONDS', -1)
    client = MagicMock()
    client.statement_execution.execute_statement.return_value = _resp(StatementState.PENDING)
    html = scr.spark_connect_report_html(DAY, client=client, email_to_group={})
    assert 'Check failed' in html
    client.statement_execution.cancel_execution.assert_called_once_with('st')
    client.warehouses.stop.assert_called()
    assert sent.call_args.args[0] == 'ERROR: spark_connect_report: query failed'
    assert JobRunCount.get(JobRunCount.job == 'spark_connect_report').failed == 1


def test_skipped_without_warehouse(monkeypatch):
    monkeypatch.delenv('SERVERLESS_BILLING_WAREHOUSE_ID')
    client = MagicMock()
    assert 'Skipped' in scr.spark_connect_report_html(DAY, client=client, email_to_group={})
    client.statement_execution.execute_statement.assert_not_called()
