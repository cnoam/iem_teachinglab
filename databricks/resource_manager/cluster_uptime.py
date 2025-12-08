import logging
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from typing import Optional

# --- Peewee Models and DB Imports ---
# NOTE: Ensure these imports correctly point to your Peewee setup file (e.g., db_operations)
# gemini 2025-11-25 13:30
from ..database.db_operations import (
    ClusterUptime,
    ClusterCumulativeUptime,
    ClusterInfo
)

# data structure that holds the Python state for a cluster.
@dataclass
class ClusterData:
    start_time: Optional[datetime] = None  # Tracks when the cluster was last turned on
    uptime: timedelta = timedelta()       # Duration since start_time
    cumulative: timedelta = timedelta()   # Total accumulated uptime
    warning_sent: bool = False
    force_terminated: bool = False
    cluster_name: str = ''

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
        cluster_info = ClusterInfo.get(ClusterInfo.cluster_id == cluster_id)

        # Convert DB fields (seconds/bool) back to Python types (timedelta/bool)
        start_ts = record.start_timestamp
        start_dt = datetime.fromtimestamp(start_ts) if start_ts else None

        return ClusterData(
            start_time=start_dt,
            uptime=timedelta(seconds=record.uptime_seconds),
            cumulative=timedelta(seconds=record.cumulative_seconds),
            warning_sent=record.warning_sent,
            force_terminated=record.force_terminated,
            cluster_name=cluster_info.cluster_name
        )

    except (ClusterUptime.DoesNotExist, ClusterInfo.DoesNotExist):
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

       If a resource was turned off and then on, we need to continue the counting.

    for DBR cluster, each time it is turned on, driver.start_time is set , so if the cluster is on, I can see for how long.

    e.g.
    for each cluster_id, keep total uptime.

    on       -------       ------* <-- need to update this inteval
    off -----       -------
    poll ^  ^  ^  ^  ^  ^  ^  ^  ^

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
    if current_data.start_time is None or abs(current_data.start_time.timestamp() - driver_start_time.timestamp()) > 1:
        # Cluster is newly turned on or restarted since last check
        logging.info(f"Cluster {id} is turned on again or started anew.")

        # Accumulate the uptime from the *previous* run into the cumulative total
        # (This handles the 'off then on' scenario)
        current_data.cumulative += current_data.uptime
        current_data.start_time = driver_start_time

    # 4. Update the current uptime and save
    current_data.uptime = current_uptime
    save_cluster_data(id, current_data)


from datetime import date, timedelta


def format_timedelta_to_hhmm(td: timedelta) -> str:
    """Converts a timedelta object to a string in HH:MM format."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    # Use f-string formatting to ensure two digits for both hours and minutes
    return f"{hours:02}:{minutes:02}"


def create_usage_report_daily(when: date) -> str:
    """
    Create an html page with the usage report of the cluster for the current day,
    using a table format and rounding time to hh:mm.
    """
    # Initialize report lines with title and table structure
    report_lines = [f"<h1>Daily Cluster Usage Report - {when}</h1>"]
    total_daily_recorded_uptime = timedelta()

    # Query all records for today from the historical cumulative table
    # NOTE: Assuming daily_records is a list/iterator of ClusterCumulativeUptime objects
    daily_records = (ClusterCumulativeUptime
                     .select(ClusterCumulativeUptime, ClusterInfo)
                     .join(ClusterInfo, on=(ClusterCumulativeUptime.cluster == ClusterInfo.cluster_id))
                     .where(ClusterCumulativeUptime.date == when))

    if not daily_records.exists():
        # If no records exist, provide a summary without an empty table
        report_lines.append(f"<p>Note: No final usage record has been written for {when} yet.</p>")
        report_lines.append(f"<h2>Total Daily Recorded Uptime: 00:00</h2>")
        return "\n".join(report_lines)

    # Start the table structure
    report_lines.append("""
        <table border="1" style="border-collapse: collapse; width: 50%;">
            <tr>
                <th style="text-align: left;">Cluster Name</th>
                <th style="text-align: right;">Daily Usage (HH:MM)</th>
            </tr>
    """)

    for record in daily_records:
        # Convert DB seconds back to timedelta
        daily_td = timedelta(seconds=record.daily_use_seconds)
        total_daily_recorded_uptime += daily_td

        # Format the daily usage to HH:MM
        formatted_time = format_timedelta_to_hhmm(daily_td)

        # Append the table row (<tr>)
        report_lines.append(f"""
            <tr>
                <td style="text-align: left;">{record.clusterinfo.cluster_name}</td>
                <td style="text-align: right;">{formatted_time}</td>
            </tr>
        """)

    # Close the table
    report_lines.append("</table>")

    # Format the total uptime
    total_formatted_time = format_timedelta_to_hhmm(total_daily_recorded_uptime)
    report_lines.append(f"<h2>Total Daily Recorded Uptime: {total_formatted_time}</h2>")

    return "\n".join(report_lines)


# gemini 2025-11-25 13:30
def create_usage_report_cumulative(db_instance) -> str:
    """
    Create an html page with the usage report of the cluster over all the measurement period.
    This function is READ-ONLY.
    """
    report_lines = ["<h1>Cumulative Cluster Usage Report</h1>", "<ul>"]
    total_cumulative_uptime = timedelta()

    with db_instance.connection_context():
        # Get all cluster records ordered by total uptime (cumulative + current live uptime)
        query = (ClusterUptime
                 .select(ClusterUptime, ClusterInfo)
                 .join(ClusterInfo, on=(ClusterUptime.id == ClusterInfo.cluster_id))
                 .order_by(ClusterUptime.cumulative_seconds.desc()))

        for record in query:
            # Calculate the full current uptime: accumulated + currently running
            cumulative_td = timedelta(seconds=record.cumulative_seconds + record.uptime_seconds)
            total_cumulative_uptime += cumulative_td
            report_lines.append(f"<li>Cluster {record.cluster_info.cluster_name}: {cumulative_td}</li>")

    report_lines.append(f"</ul><h2>Total Uptime Measured: {total_cumulative_uptime}</h2>")
    return "\n".join(report_lines)
