import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta
from peewee import SqliteDatabase

# Imports from your application
from end_of_day_operations import send_usage_report
from databricks.database.db_operations import ClusterUptime, ClusterCumulativeUptime

# Define Test DB
TEST_DB = SqliteDatabase(':memory:')

# --- Fixture (Reused from your other tests) ---
@pytest.fixture(scope='function', autouse=True)
def setup_teardown_db():
    ClusterUptime.bind(TEST_DB)
    ClusterCumulativeUptime.bind(TEST_DB)

    # Open connection for the duration of the test
    with TEST_DB.connection_context():
        TEST_DB.create_tables([ClusterUptime, ClusterCumulativeUptime])
        yield
        TEST_DB.drop_tables([ClusterUptime, ClusterCumulativeUptime])

    ClusterUptime.bind(None)
    ClusterCumulativeUptime.bind(None)

# --- The Unit Test ---

@patch('end_of_day_operations.send_emails')
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

    # We create 'yesterday's' data.
    # NOTE: Since the reporting function queries for `date.today()`,
    # we effectively insert data for 'today' relative to the test execution
    # so the report finds it.
    report_date = date.today()
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
    assert "1:30:00" in body_html
    # Check structure
    assert "<h1>Daily Cluster Usage Report" in body_html