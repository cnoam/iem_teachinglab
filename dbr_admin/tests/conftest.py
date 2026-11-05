import pytest

from dbr_admin.resource_manager import warehouse_stop


@pytest.fixture(autouse=True)
def _no_real_sleep_in_warehouse_stop(monkeypatch):
    monkeypatch.setattr(warehouse_stop, '_sleep', lambda s: None)
