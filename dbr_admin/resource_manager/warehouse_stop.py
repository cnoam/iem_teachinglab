"""
Stop a dedicated admin SQL warehouse after a scheduled system-table query.

Pitfall (live-tested 2026-11-05 on the serverless "Admin Checks (no students)" warehouse):
calling warehouses.stop() right after a system.billing.usage query returns SUCCEEDED
is silently undone -- the warehouse goes STARTING -> RUNNING again within ~0.4s, with no
new query in its history, and then idles until its auto_stop_mins. A trivial
`select 1` does not trigger this, and waiting ~10s before stopping avoids it.
So: wait SETTLE_SECONDS, stop, check after VERIFY_SECONDS, and stop once more if it
came back. Never raises -- a failed stop only costs auto_stop_mins of idle time.
"""
import logging
import time

from databricks.sdk.service.sql import State

SETTLE_SECONDS = 10
VERIFY_SECONDS = 5
_AWAKE = (State.STARTING, State.RUNNING)

# Module-level so tests can replace it (tests/conftest.py makes it a no-op).
_sleep = time.sleep


def stop_warehouse(client, warehouse_id: str, logger: logging.Logger) -> bool:
    """Returns True if the warehouse was seen stopping/stopped, False otherwise (logged)."""
    try:
        _sleep(SETTLE_SECONDS)
        for attempt in (1, 2):
            client.warehouses.stop(warehouse_id)
            _sleep(VERIFY_SECONDS)
            state = client.warehouses.get(warehouse_id).state
            if state not in _AWAKE:
                return True
            logger.info(f"warehouse {warehouse_id} is {state} after stop attempt {attempt}")
        logger.warning(f"warehouse {warehouse_id} still {state} after 2 stop attempts; "
                       f"it will idle until its auto-stop")
    except Exception as ex:
        logger.warning(f"Could not stop warehouse {warehouse_id}: {ex}")
    return False
