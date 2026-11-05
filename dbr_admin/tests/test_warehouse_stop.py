# stop_warehouse(): waits before stopping, re-stops once if the warehouse wakes back up,
# never raises. Sleeps are no-ops here (tests/conftest.py).
from unittest.mock import MagicMock

from databricks.sdk.service.sql import State

from dbr_admin.resource_manager import warehouse_stop
from dbr_admin.resource_manager.warehouse_stop import stop_warehouse


def _client(*states):
    c = MagicMock()
    c.warehouses.get.side_effect = [MagicMock(state=s) for s in states]
    return c


def test_waits_before_first_stop(monkeypatch):
    calls = []
    c = _client(State.STOPPED)
    c.warehouses.stop.side_effect = lambda w: calls.append('stop')
    monkeypatch.setattr(warehouse_stop, '_sleep', lambda s: calls.append(f'sleep{s}'))
    assert stop_warehouse(c, 'wh', MagicMock())
    assert calls[:2] == [f'sleep{warehouse_stop.SETTLE_SECONDS}', 'stop']


def test_stops_once_when_it_stays_stopped():
    c = _client(State.STOPPING)
    assert stop_warehouse(c, 'wh', MagicMock())
    c.warehouses.stop.assert_called_once_with('wh')


def test_restops_when_warehouse_wakes_back_up():
    c = _client(State.STARTING, State.STOPPED)
    assert stop_warehouse(c, 'wh', MagicMock())
    assert c.warehouses.stop.call_count == 2


def test_gives_up_after_two_attempts_with_warning():
    c = _client(State.RUNNING, State.RUNNING)
    logger = MagicMock()
    assert not stop_warehouse(c, 'wh', logger)
    assert c.warehouses.stop.call_count == 2
    logger.warning.assert_called_once()


def test_never_raises():
    c = MagicMock()
    c.warehouses.stop.side_effect = RuntimeError("boom")
    logger = MagicMock()
    assert not stop_warehouse(c, 'wh', logger)
    logger.warning.assert_called_once()
