# test_end_of_day_ops.py
import pytest
from datetime import date, timedelta
from peewee import SqliteDatabase, DoesNotExist

# Assuming log_daily_uptime is in this file or imported from it
from ..end_of_day_operations import log_daily_uptime

# Import models from where they are defined
from databricks.database.db_operations import (
    ClusterUptime,
    ClusterCumulativeUptime
)

TEST_DB = SqliteDatabase(':memory:')

# --- Fixture for In-Memory DB Setup (Essential for Atomic Testing) ---
@pytest.fixture(scope='function', autouse=True)
def setup_teardown_db():
    """
    Binds models to a clean in-memory DB for each test function
    and handles connection management.
    """
    # 1. BIND to the TEST_DB
    ClusterUptime.bind(TEST_DB)
    ClusterCumulativeUptime.bind(TEST_DB)

    with TEST_DB.connection_context():
        # 2. CONNECT & CREATE
        # TEST_DB.connect() Already done in the context manager above
        TEST_DB.create_tables([ClusterUptime, ClusterCumulativeUptime])
        yield

        # 3. TEARDOWN (Unbind and close)
        TEST_DB.drop_tables([ClusterUptime, ClusterCumulativeUptime])
    #TEST_DB.close()

    # 4. CRITICAL: Unbind models to clear the global class state completely
    # This restores the models to a fully unbound state.
    ClusterUptime.bind( None)
    ClusterCumulativeUptime.bind( None)



def test_log_daily_uptime_functionality():
    """
    Tests that log_daily_uptime correctly logs yesterday's usage
    and resets today's live uptime counter.
    """
    yesterday = date.today() - timedelta(days=1)

    # 1. SETUP: Create two initial live records

    # Cluster A: Has run 1 hour previously, and 30 minutes in the current cycle
    ClusterUptime.create(
        id='cluster-A',
        cumulative_seconds=3600,
        uptime_seconds=1800  # 30 minutes of current cycle
    )
    # Cluster B: Only 10 minutes in the current cycle
    ClusterUptime.create(
        id='cluster-B',
        cumulative_seconds=0,
        uptime_seconds=600  # 10 minutes of current cycle
    )

    # Ensure the cumulative table is initially empty for yesterday
    with pytest.raises(DoesNotExist):
        ClusterCumulativeUptime.get(ClusterCumulativeUptime.date == yesterday)

    # 2. ACTION: Run the end-of-day logging job
    log_daily_uptime()

    # 3. VERIFICATION - LOGGING: Check the historical table
    # Cluster A should have logged 1800 seconds for yesterday
    log_A = ClusterCumulativeUptime.get(
        (ClusterCumulativeUptime.cluster == 'cluster-A') &
        (ClusterCumulativeUptime.date == yesterday)
    )
    assert log_A.daily_use_seconds == 1800

    # Cluster B should have logged 600 seconds for yesterday
    log_B = ClusterCumulativeUptime.get(
        (ClusterCumulativeUptime.cluster == 'cluster-B') &
        (ClusterCumulativeUptime.date == yesterday)
    )
    assert log_B.daily_use_seconds == 600

    # 4. VERIFICATION - RESET: Check the live table
    live_A = ClusterUptime.get(ClusterUptime.id == 'cluster-A')
    live_B = ClusterUptime.get(ClusterUptime.id == 'cluster-B')

    # The 'uptime_seconds' (current run cycle) must be reset to 0
    assert live_A.uptime_seconds == 0
    assert live_B.uptime_seconds == 0

    # The 'cumulative_seconds' (historical total) must NOT be reset
    # It should still be the initial 3600 (as update_cumulative_uptime handles the roll-up)
    assert live_A.cumulative_seconds == 3600
