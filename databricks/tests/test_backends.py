# test_backends.py
# Step 1 of databricks/serverless_quota_plan.md: the UsageBackend interface,
# ClassicBackend (thin wrapper -- delegates to the existing classic
# functions, no reimplementation) and the ServerlessBackend stub.

import pytest
from unittest.mock import patch, MagicMock

from databricks.resource_manager.backends.factory import get_backend
from databricks.resource_manager.backends.classic import ClassicBackend
from databricks.resource_manager.backends.serverless import ServerlessBackend


# --- Factory: QUOTA_MODE selection ---

def test_get_backend_defaults_to_classic(monkeypatch):
    monkeypatch.delenv('QUOTA_MODE', raising=False)
    assert isinstance(get_backend(), ClassicBackend)


def test_get_backend_classic_explicit(monkeypatch):
    monkeypatch.setenv('QUOTA_MODE', 'classic')
    assert isinstance(get_backend(), ClassicBackend)


def test_get_backend_serverless(monkeypatch):
    monkeypatch.setenv('QUOTA_MODE', 'serverless')
    assert isinstance(get_backend(), ServerlessBackend)


def test_get_backend_case_and_whitespace_insensitive(monkeypatch):
    monkeypatch.setenv('QUOTA_MODE', '  Serverless  ')
    assert isinstance(get_backend(), ServerlessBackend)


def test_get_backend_unknown_mode_raises(monkeypatch):
    monkeypatch.setenv('QUOTA_MODE', 'bogus')
    with pytest.raises(ValueError, match='bogus'):
        get_backend()


# --- ClassicBackend: proves it delegates, doesn't reimplement ---

@patch('databricks.resource_manager.backends.classic._poll_clusters_main')
def test_classic_backend_collect_and_enforce_delegates(mock_main):
    ClassicBackend().collect_and_enforce()
    mock_main.assert_called_once_with()


@patch('databricks.resource_manager.backends.classic._restore_cluster_permissions')
def test_classic_backend_restore_delegates(mock_restore):
    logger = MagicMock()
    ClassicBackend().restore('host', 'token', logger)
    mock_restore.assert_called_once_with('host', 'token', logger)


@patch('databricks.resource_manager.backends.classic._log_daily_uptime')
def test_classic_backend_roll_up_and_reset_delegates(mock_log):
    prod_db = MagicMock()
    logger = MagicMock()
    ClassicBackend().roll_up_and_reset(prod_db, logger)
    mock_log.assert_called_once_with(prod_db, logger)


@patch('databricks.resource_manager.backends.classic._create_usage_report_daily')
def test_classic_backend_report_delegates(mock_report):
    mock_report.return_value = '<html/>'
    result = ClassicBackend().report('2026-09-16')
    mock_report.assert_called_once_with('2026-09-16')
    assert result == '<html/>'


# --- ServerlessBackend: Step 1 stub, every method raises NotImplementedError ---

@pytest.mark.parametrize('call', [
    lambda b: b.collect_and_enforce(),
    lambda b: b.restore('host', 'token', MagicMock()),
    lambda b: b.roll_up_and_reset(MagicMock(), MagicMock()),
    lambda b: b.report('2026-09-16'),
])
def test_serverless_backend_not_implemented(call):
    with pytest.raises(NotImplementedError, match='serverless_quota_plan.md'):
        call(ServerlessBackend())
