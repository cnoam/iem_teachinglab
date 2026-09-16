# test_backends.py
# Step 1 of databricks/serverless_quota_plan.md: the UsageBackend interface,
# ClassicBackend (thin wrapper -- delegates to the existing classic
# functions, no reimplementation), and the get_backend() factory.
#
# ServerlessBackend's own behavior (real implementation as of Step 2) is
# covered in test_serverless_backend.py, not here.

import pytest
from unittest.mock import patch, MagicMock

from dbr_admin.resource_manager.backends.factory import get_backend
from dbr_admin.resource_manager.backends.classic import ClassicBackend
from dbr_admin.resource_manager.backends.serverless import ServerlessBackend


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

@patch('dbr_admin.resource_manager.backends.classic._poll_clusters_main')
def test_classic_backend_collect_and_enforce_delegates(mock_main):
    ClassicBackend().collect_and_enforce()
    mock_main.assert_called_once_with()


@patch('dbr_admin.resource_manager.backends.classic._restore_cluster_permissions')
def test_classic_backend_restore_delegates(mock_restore):
    logger = MagicMock()
    ClassicBackend().restore('host', 'token', logger)
    mock_restore.assert_called_once_with('host', 'token', logger)


@patch('dbr_admin.resource_manager.backends.classic._log_daily_uptime')
def test_classic_backend_roll_up_and_reset_delegates(mock_log):
    prod_db = MagicMock()
    logger = MagicMock()
    ClassicBackend().roll_up_and_reset(prod_db, logger)
    mock_log.assert_called_once_with(prod_db, logger)


@patch('dbr_admin.resource_manager.backends.classic._create_usage_report_daily')
def test_classic_backend_report_delegates(mock_report):
    mock_report.return_value = '<html/>'
    result = ClassicBackend().report('2026-09-16')
    mock_report.assert_called_once_with('2026-09-16')
    assert result == '<html/>'


