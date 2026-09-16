# test_serverless_billing.py
# system.billing.usage backstop poll (plan 2.6a). Best-effort: must never
# raise out of backstop_check(), whatever goes wrong. Against a mocked SDK
# client -- no network calls.

from unittest.mock import patch, MagicMock

from databricks.sdk.service.sql import StatementResponse, StatementStatus, StatementState, ResultData

from dbr_admin.resource_manager.serverless_billing import backstop_check, fetch_billed_seconds_per_user


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
