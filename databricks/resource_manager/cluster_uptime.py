import logging
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from typing import Optional

# data structure that holds the Python state for a cluster.
@dataclass
class ClusterData:
    start_time: Optional[datetime] = None  # Tracks when the cluster was last turned on
    uptime: timedelta = timedelta()       # Duration since start_time
    cumulative: timedelta = timedelta()   # Total accumulated uptime
    warning_sent: bool = False
    force_terminated: bool = False
    cluster_name: str = ''

# --- Peewee Models and DB Imports ---
# NOTE: Ensure these imports correctly point to your Peewee setup file (e.g., db_operations)
from databricks.database.db_operations import (
    ClusterUptime,
    ClusterCumulativeUptime
)

logging.basicConfig(level=logging.INFO)


def get_or_create_cluster_data(cluster_id: str) -> ClusterData:
    """
    Retrieves or initializes a ClusterData object from the DB.

    Returns:
        ClusterData: The current state of the cluster's uptime data.
    """
    try:
        # Try to retrieve the existing record
        record = ClusterUptime.get(ClusterUptime.id == cluster_id)

        # Convert DB fields (seconds/bool) back to Python types (timedelta/bool)
        start_ts = record.start_timestamp
        start_dt = datetime.fromtimestamp(start_ts) if start_ts else None

        return ClusterData(
            start_time=start_dt,
            uptime=timedelta(seconds=record.uptime_seconds),
            cumulative=timedelta(seconds=record.cumulative_seconds),
            warning_sent=record.warning_sent,
            force_terminated=record.force_terminated,
            #cluster_name = record.cluster_name
        )

    except ClusterUptime.DoesNotExist:
        # If record does not exist, create a clean object
        return ClusterData()


def save_cluster_data(cluster_id: str, data: ClusterData):
    """
    Saves the ClusterData object back to the database, handling creation/update.
    """
    # Convert Python types (datetime/timedelta) to DB storage types (timestamp/seconds)
    start_ts = data.start_time.timestamp() if data.start_time else None
    uptime_sec = data.uptime.total_seconds()
    cumulative_sec = data.cumulative.total_seconds()

    # Use Peewee's .create or .get_or_create for robust upsert logic
    ClusterUptime.replace(
        id=cluster_id,
        start_timestamp=start_ts,
        uptime_seconds=uptime_sec,
        cumulative_seconds=cumulative_sec,
        warning_sent=data.warning_sent,
        force_terminated=data.force_terminated
    ).execute()


def update_cumulative_uptime(cluster: dict):
    """
    Update the total uptime of resource in our DB.
    """
    assert 'driver' in cluster.keys()  # only running cluster is provided
    driver = cluster['driver']
    id = cluster['cluster_id']

    # 1. Retrieve current data
    current_data = get_or_create_cluster_data(id)

    # 2. Calculate current runtime
    # Timestamps are typically in milliseconds, convert to seconds for datetime.fromtimestamp
    driver_start_ts_ms = driver['start_timestamp']
    driver_start_time = datetime.fromtimestamp(driver_start_ts_ms / 1000)
    current_uptime = datetime.now() - driver_start_time

    # 3. Check for cluster restart
    if current_data.start_time is None or current_data.start_time != driver_start_time:
        # Cluster is newly turned on or restarted since last check
        logging.info(f"Cluster {id} is turned on again or started anew.")

        # Accumulate the uptime from the *previous* run into the cumulative total
        # (This handles the 'off then on' scenario)
        current_data.cumulative += current_data.uptime
        current_data.start_time = driver_start_time

    # 4. Update the current uptime and save
    current_data.uptime = current_uptime
    save_cluster_data(id, current_data)


def create_usage_report_daily() -> str:
    """
    Create an html page with the usage report of the cluster for the current day.
    This function is NOW READ-ONLY and queries the *historical* daily usage.
    """
    today = date.today()
    report_lines = [f"<h1>Daily Cluster Usage Report - {today}</h1>", "<ul>"]
    total_daily_recorded_uptime = timedelta()


    # Query all records for today from the historical cumulative table
    daily_records = ClusterCumulativeUptime.select().where(
        ClusterCumulativeUptime.date == today
    )

    for record in daily_records:
        # Convert DB seconds back to timedelta
        daily_td = timedelta(seconds=record.daily_use_seconds)
        total_daily_recorded_uptime += daily_td
        report_lines.append(f"<li>Cluster {record.cluster.id}: {daily_td}</li>") # Access FK ID via record.cluster.id

    report_lines.append(f"</ul><h2>Total Daily Recorded Uptime: {total_daily_recorded_uptime}</h2>")

    # If no records exist for today, this provides a more useful summary:
    if not daily_records.exists():
        report_lines.append("<p>Note: No final usage record has been written for today yet.</p>")

    return "\n".join(report_lines)


def create_usage_report_cumulative(db_instance) -> str:
    """
    Create an html page with the usage report of the cluster over all the measurement period.
    This function is READ-ONLY.
    """
    report_lines = ["<h1>Cumulative Cluster Usage Report</h1>", "<ul>"]
    total_cumulative_uptime = timedelta()

    with db_instance.connection_context():
        # Get all cluster records ordered by total uptime (cumulative + current live uptime)
        for cluster in ClusterUptime.select().order_by(ClusterUptime.cumulative_seconds.desc()):
            # Calculate the full current uptime: accumulated + currently running
            cumulative_td = timedelta(seconds=cluster.cumulative_seconds + cluster.uptime_seconds)
            total_cumulative_uptime += cumulative_td
            report_lines.append(f"<li>Cluster {cluster.id}: {cumulative_td}</li>")

    report_lines.append(f"</ul><h2>Total Uptime Measured: {total_cumulative_uptime}</h2>")
    return "\n".join(report_lines)