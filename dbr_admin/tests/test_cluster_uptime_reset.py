"""
Regression tests for the "absolute time re-import" bug:

After the midnight reset (end_of_day_operations truncates cluster_uptimes),
the first poll must NOT re-import runtime accumulated before midnight for
clusters that have been running since the previous day.

Ported from the quota-checker server's unpublished commit f39936f
(2026-07-08, pre-dates the databricks/ -> dbr_admin/ rename) -- see
serverless_quota_plan.md's deployment notes for context.
"""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
from peewee import SqliteDatabase

from dbr_admin.database.db_operations import (
    ClusterUptime, ClusterCumulativeUptime, ClusterInfo
)
from dbr_admin.resource_manager.cluster_uptime import update_cumulative_uptime
from dbr_admin.end_of_day_operations import log_daily_uptime

TEST_DB = SqliteDatabase(':memory:')


@pytest.fixture(scope='function', autouse=True)
def setup_teardown_db():
    ClusterUptime.bind(TEST_DB)
    ClusterCumulativeUptime.bind(TEST_DB)
    ClusterInfo.bind(TEST_DB)

    with TEST_DB.connection_context():
        TEST_DB.create_tables([ClusterUptime, ClusterCumulativeUptime, ClusterInfo])
        yield
        TEST_DB.drop_tables([ClusterUptime, ClusterCumulativeUptime, ClusterInfo])

    ClusterUptime.bind(None)
    ClusterCumulativeUptime.bind(None)
    ClusterInfo.bind(None)


def _make_cluster(cluster_id: str, driver_start: datetime) -> dict:
    return {
        'cluster_id': cluster_id,
        'driver': {'start_timestamp': driver_start.timestamp() * 1000}
    }


def _patched_now(fake_now: datetime):
    """Patch datetime inside cluster_uptime so now() is fixed but the rest works."""
    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = fake_now
    return patch('dbr_admin.resource_manager.cluster_uptime.datetime', mock_dt)


def test_first_poll_after_reset_does_not_reimport_yesterday():
    """
    Cluster started yesterday 18:00 and is still running.
    Midnight reset truncated the table. First poll at 00:15 today
    must record ~15 minutes, NOT ~6h15m since cluster start.
    """
    today = date.today()
    poll_time = datetime.combine(today, datetime.min.time()) + timedelta(minutes=15)
    driver_start = datetime.combine(today - timedelta(days=1),
                                    datetime.min.time()) + timedelta(hours=18)

    # Simulate the state right after end_of_day: table is empty
    ClusterUptime.create(cluster_id='c1', uptime_seconds=99999)
    log_daily_uptime(TEST_DB, MagicMock())
    assert ClusterUptime.select().count() == 0

    with _patched_now(poll_time):
        update_cumulative_uptime(_make_cluster('c1', driver_start))

    record = ClusterUptime.get(ClusterUptime.cluster_id == 'c1')
    total = record.uptime_seconds + record.cumulative_seconds
    assert total == pytest.approx(15 * 60, abs=1), (
        f"Expected ~15 minutes since midnight, got {total/60:.0f} minutes "
        f"(pre-midnight runtime was re-imported)"
    )


def test_new_record_cluster_started_today():
    """
    Cluster started today at 00:03 (after the reset), first poll 00:15:
    should count from cluster start, i.e. ~12 minutes.
    """
    today = date.today()
    midnight = datetime.combine(today, datetime.min.time())
    poll_time = midnight + timedelta(minutes=15)
    driver_start = midnight + timedelta(minutes=3)

    with _patched_now(poll_time):
        update_cumulative_uptime(_make_cluster('c2', driver_start))

    record = ClusterUptime.get(ClusterUptime.cluster_id == 'c2')
    assert record.uptime_seconds + record.cumulative_seconds == pytest.approx(12 * 60, abs=1)


def test_genuine_restart_counts_from_restart_time():
    """
    Existing record (no reset): cluster restarted 10 minutes ago.
    Previous session uptime is archived to cumulative; new session counts
    from the restart time.
    """
    today = date.today()
    noon = datetime.combine(today, datetime.min.time()) + timedelta(hours=12)
    old_start = noon - timedelta(hours=3)
    restart_time = noon - timedelta(minutes=10)

    ClusterUptime.create(
        cluster_id='c3',
        start_time=old_start,
        last_poll_time=noon - timedelta(minutes=20),
        uptime_seconds=600,
        cumulative_seconds=0,
    )

    with _patched_now(noon):
        update_cumulative_uptime(_make_cluster('c3', restart_time))

    record = ClusterUptime.get(ClusterUptime.cluster_id == 'c3')
    assert record.cumulative_seconds == pytest.approx(600, abs=1)   # archived old session
    assert record.uptime_seconds == pytest.approx(10 * 60, abs=1)   # since restart
