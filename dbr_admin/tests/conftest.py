import pytest

from dbr_admin.resource_manager import warehouse_stop


@pytest.fixture(autouse=True)
def _no_real_sleep_in_warehouse_stop(monkeypatch):
    monkeypatch.setattr(warehouse_stop, '_sleep', lambda s: None)


@pytest.fixture(autouse=True)
def _no_real_error_emails(monkeypatch):
    # error_report falls back to the real Azure sender when none is passed -- never in tests.
    from dbr_admin.resource_manager import error_report

    def _refuse():
        raise AssertionError("test tried to send a real email via error_report")
    monkeypatch.setattr(error_report, '_default_send', _refuse)
    monkeypatch.setattr(warehouse_stop, '_report_error', lambda *a, **kw: False)
    monkeypatch.setattr(warehouse_stop, '_report_ok', lambda *a, **kw: 0)
