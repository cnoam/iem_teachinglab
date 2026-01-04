# test_poll_clusters.py
# 2025-11-19 written with the help of Gemini 2.5.
# there are delicate db handling issues here that are worth watching

# this code use mocks of many functions, including the DBR API

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta
from peewee import SqliteDatabase
from databricks.poll_clusters import main, check_update_running_clusters, get_emails_address

# Import models and ORM helpers
from databricks.database.db_operations import ClusterUptime, ClusterCumulativeUptime, ClusterInfo
from databricks.resource_manager.cluster_uptime import get_or_create_cluster_record


# --- Fixture for In-Memory DB Setup ---
# --- New, Temporary In-Memory DB Object for Testing ---
# This ensures we are not polluting or relying on the main 'db' object.
TEST_DB = SqliteDatabase(':memory:')

@pytest.fixture(scope='function', autouse=True)
def setup_teardown_db():
    """
    Binds models to a clean in-memory DB for each test function
    and handles connection management.
    """
    # 1. BIND to the TEST_DB
    ClusterUptime.bind(TEST_DB)
    ClusterCumulativeUptime.bind(TEST_DB)
    ClusterInfo.bind(TEST_DB)

    with TEST_DB.connection_context():
        # 2. CONNECT & CREATE
        # TEST_DB.connect() Already done in the context manager above
        TEST_DB.create_tables([ClusterUptime, ClusterCumulativeUptime, ClusterInfo])
        yield

        # 3. TEARDOWN (Unbind and close)
        TEST_DB.drop_tables([ClusterUptime, ClusterCumulativeUptime, ClusterInfo])
    #TEST_DB.close()

    # 4. CRITICAL: Unbind models to clear the global class state completely
    # This restores the models to a fully unbound state.
    ClusterUptime.bind( None)
    ClusterCumulativeUptime.bind( None)
    ClusterInfo.bind(None)


# --- Test Utility Data ---

def get_mock_databricks_clusters(cluster_data):
    """
    Generates mock return data for client.get_clusters() based on the test scenario.
    """
    clusters = []
    for cid, state in cluster_data.items():
        is_running = state['status'] == 'RUNNING'
        cluster = {
            'cluster_id': cid,
            'cluster_name': f'cluster_{cid}',
            'state': state['status'],
        }
        if is_running:
            cluster['driver'] = {
                'start_timestamp': int(state['start_time'].timestamp() * 1000)
            }
        clusters.append(cluster)
    return clusters


# --- The Complex Scenario Test ---


@patch('databricks.poll_clusters.send_emails')
@patch('databricks.poll_clusters.os')
@patch('databricks.poll_clusters.DataBricksGroups')
@patch('databricks.poll_clusters.DataBricksClusterOps')
#@patch('poll_clusters.update_cumulative_uptime')

# Mock datetime for time travel
# but keep the time_delta unchanged
@patch('databricks.poll_clusters.datetime')
def test_cluster_monitoring_scenario(mock_dt, #update_cumulative_uptime,
                                     MockClusterOps, MockGroups, mock_os,
                                     mock_send_emails):
    """
    Simulates the 3-cluster scenario, verifying termination and warning logic.
    """

    #  Tell the mocked datetime object to use the real timedelta class
    # This allows threshold variables to be actual datetime.timedelta objects.
    mock_dt.timedelta = timedelta

    # --- 1. SETUP MOCKS & ENV ---

    # Configure time mocks (Time starts 4 hours ago for simulation)
    now = datetime.now()
    mock_dt.now.return_value = now

    # Configure environment variables (WARNING @ 3h, TERMINATE @ 3.5h)
    mock_os.getenv.side_effect = lambda x, default=None: {
        'DATABRICKS_HOST': 'test-host',
        'DATABRICKS_TOKEN': 'test-token',
        'DATABRICKS_MAX_UPTIME': '210',  # 3.5 hours = 210 minutes
        'DATABRICKS_WARN_UPTIME': '180',  # 3.0 hours = 180 minutes
        'ADMIN_EMAIL': 'admin@test.com'
    }.get(x, default)

    mock_client_instance = MockClusterOps.return_value
    mock_groups_instance = MockGroups.return_value
    mock_groups_instance.get_group_members.return_value = [{'user_name': 'test@user.com'}]

    MINUTE = timedelta(minutes=1)

    # --- 2. INITIAL DB STATE (Simulate cumulative state) ---
    # note: use cluster id = 'number' so we can generate the mock cluster name from it

    # Cluster 1 (Off) - Last start time 4 hours ago , was up for 2 hours
    ClusterUptime.create(
        cluster_id='1',
        cumulative_seconds= 7200,
        uptime_seconds=0,  # Currently off
        start_time=(now - timedelta(hours=4))
    )
    # Cluster 2 (ON)  for 2 hours before, and now 1h10m  > 3h
    ClusterUptime.create(
        cluster_id='2',
        cumulative_seconds= 7200,
        uptime_seconds= 70 * MINUTE.total_seconds(),
        start_time=(now - 70 * MINUTE)
    )
    # Cluster 3 (ON), for 3 hours before, and now 1h40m > 3.5h
    ClusterUptime.create(
        cluster_id='3',
        cumulative_seconds= 3 * 3600,
        uptime_seconds=100 * MINUTE.total_seconds(),
        start_time=(now - 100 * MINUTE)
    )

    # --- 3. CLUSTER API MOCK DATA ---

    # Define the simplified cluster data for the mock generation
    scenario_data = {
        # Cluster 1: OFF (State: TERMINATED)
        '1': {
            'status': 'TERMINATED',
            'start_time': now - timedelta(hours=4) # Use the same time for consistency
        },
        # Cluster 2: ON (State: RUNNING, 70min into run)
        '2': {
            'status': 'RUNNING',
            'start_time': now - 70*MINUTE
        },
        # Cluster 3: ON (State: RUNNING, 100min into run)
        '3': {
            'status': 'RUNNING',
            'start_time': now - 100*MINUTE
        },
    }

    mock_client_instance.get_clusters.return_value = get_mock_databricks_clusters(scenario_data)

    # --- 4. EXECUTION ---

    # We mock 'update_cumulative_uptime' because its internal logic is tested elsewhere.
    # We need the times to be checked based on the initial DB state + current runtime.

    main() # the TEST_DB is already connected in the fixture, so no need to pass it

    # --- 5. ASSERTIONS ---

    # Check Termination
    mock_client_instance.delete_cluster.assert_called_once_with('cluster_3')

    # Check Email Counts
    # Cluster 3 (Terminate) and Cluster 2 (Warning) should each trigger one email.
    assert mock_send_emails.call_count == 2

    # Check Warning Email (Cluster 2)
    # The 'subject' is passed as keyword args, so we must use kwargs rather than args.
    warning_call = mock_send_emails.call_args_list[0]
    assert 'is working for a long time' in warning_call.kwargs['subject']

    # Cluster 2: Should have warning_sent=True
    c2 = ClusterUptime.get(ClusterUptime.cluster_id == '2')
    assert c2.warning_sent is True
    assert c2.force_terminated is False

    # Cluster 3: Should have force_terminated=True
    c3 = ClusterUptime.get(ClusterUptime.cluster_id == '3')
    assert c3.warning_sent is False  # because we ran it once only
    assert c3.force_terminated is True

    # Cluster 1: Should be untouched
    c1 = ClusterUptime.get(ClusterUptime.cluster_id == '1')
    assert c1.warning_sent is False
    assert c1.force_terminated is False