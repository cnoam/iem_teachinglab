# test_serverless_billing.py
# system.billing.usage backstop poll (plan 2.6a). Best-effort: must never
# raise out of backstop_check(), whatever goes wrong.

from unittest.mock import patch, MagicMock

from databricks.resource_manager.serverless_billing import backstop_check, fetch_billed_seconds_per_user

MOD = 'databricks.resource_manager.serverless_billing'


def test_backstop_check_skips_when_no_warehouse_configured():
    logger = MagicMock()
    result = backstop_check('host', 'token', warehouse_id=None,
                             email_to_group={}, backstop_seconds=100, logger=logger)
    assert result == set()
    logger.info.assert_called_once()


@patch(f'{MOD}.fetch_billed_seconds_per_user')
def test_backstop_check_flags_group_over_backstop(mock_fetch):
    mock_fetch.return_value = {'a@test.com': 20000.0, 'b@test.com': 10.0}
    result = backstop_check('host', 'token', 'wh-id',
                             email_to_group={'a@test.com': 'group_01', 'b@test.com': 'group_02'},
                             backstop_seconds=18000, logger=MagicMock())
    assert result == {'group_01'}


@patch(f'{MOD}.fetch_billed_seconds_per_user')
def test_backstop_check_never_raises_on_failure(mock_fetch):
    mock_fetch.side_effect = RuntimeError("no access to system.billing.usage")
    logger = MagicMock()
    result = backstop_check('host', 'token', 'wh-id', {}, 100, logger)
    assert result == set()
    logger.warning.assert_called_once()


@patch(f'{MOD}._submit_and_wait')
def test_fetch_billed_seconds_per_user_parses_rows(mock_submit):
    mock_submit.return_value = {
        'status': {'state': 'SUCCEEDED'},
        'result': {'data_array': [['a@test.com', 3600.0], ['b@test.com', None]]},
    }
    result = fetch_billed_seconds_per_user('host', 'token', 'wh-id')
    assert result == {'a@test.com': 3600.0, 'b@test.com': 0.0}


@patch(f'{MOD}._submit_and_wait')
def test_fetch_billed_seconds_per_user_raises_on_query_failure(mock_submit):
    mock_submit.return_value = {'status': {'state': 'FAILED'}}
    import pytest
    with pytest.raises(RuntimeError):
        fetch_billed_seconds_per_user('host', 'token', 'wh-id')
