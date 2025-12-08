import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta
from peewee import SqliteDatabase

# Imports from your application
from databricks.end_of_day_operations import send_usage_report
from databricks.database.db_operations import ClusterUptime, ClusterCumulativeUptime, ClusterInfo
from peewee import SqliteDatabase, DoesNotExist

from ..end_of_day_operations import log_daily_uptime
# Define Test DB
TEST_DB = SqliteDatabase(':memory:')

# --- Fixture (Reused from your other tests) ---
@pytest.fixture(scope='function', autouse=True)
def setup_teardown_db():
    ClusterUptime.bind(TEST_DB)
    ClusterCumulativeUptime.bind(TEST_DB)
    ClusterInfo.bind(TEST_DB)

    # Open connection for the duration of the test
    with TEST_DB.connection_context():
        TEST_DB.create_tables([ClusterUptime, ClusterCumulativeUptime, ClusterInfo])
        yield
        TEST_DB.drop_tables([ClusterUptime, ClusterCumulativeUptime, ClusterInfo])

    ClusterUptime.bind(None)
    ClusterCumulativeUptime.bind(None)
    ClusterInfo.bind(None)

# --- The Unit Test ---

@patch('databricks.end_of_day_operations.send_emails')
def test_send_usage_report_correctness(mock_send_emails):
    """
    Verifies that send_usage_report:
    1. Reads the correct data from the DB.
    2. Formats the HTML correctly.
    3. Sends the email to the specified recipient.
    """

    # 1. SETUP: Create DB Data
    # We need a parent cluster record to satisfy the ForeignKey constraint
    cluster_id = "cluster_test_report"
    ClusterUptime.create(id=cluster_id)
    ClusterInfo.create(cluster_id=cluster_id, cluster_name="cluster_test_report_name")
    # We create 'yesterday's' data.
    # NOTE: Since the reporting function queries for `date.today()`,
    # we effectively insert data for 'today' relative to the test execution
    # so the report finds it.
    report_date = date.today() - timedelta(days=1)
    seconds_used = 3600 + 1800  # 1 hour, 30 minutes = 5400 seconds

    ClusterCumulativeUptime.create(
        cluster=cluster_id,
        date=report_date,
        daily_use_seconds=seconds_used # Matches the field name in your DB model
    )

    # 2. EXECUTE
    mock_logger = MagicMock()
    recipient_email = "boss@company.com"

    # Call the function under test
    send_usage_report(recipient_email, mock_logger)

    # 3. ASSERTIONS

    # A. Verify email was sent exactly once
    mock_send_emails.assert_called_once()

    # B. Extract arguments to verify content
    call_kwargs = mock_send_emails.call_args.kwargs
    subject = call_kwargs.get('subject', '') # or call_kwargs['args'][0] if positional
    body_html = call_kwargs['body']
    recipients = call_kwargs['recipients']

    # C. Verify Recipient
    assert recipients == [recipient_email]

    # D. Verify Subject
    assert "Daily cluster usage report" in subject

    # E. Verify HTML Body Content (The most important part)
    # Check for the cluster ID
    assert cluster_id in body_html
    # Check for the formatted duration (1:30:00)
    # The timedelta string for 5400 seconds is usually "1:30:00"
    assert "01:30" in body_html
    # Check structure
    assert "<h1>Daily Cluster Usage Report" in body_html


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
    # Cluster A should have logged 3600 + 1800 = 5400 seconds for yesterday
    log_A = ClusterCumulativeUptime.get(
        (ClusterCumulativeUptime.cluster == 'cluster-A') &
        (ClusterCumulativeUptime.date == yesterday)
    )
    assert log_A.daily_use_seconds == 5400

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

    # The 'cumulative_seconds' (historical total) must be reset as well
    assert live_A.cumulative_seconds == 0
