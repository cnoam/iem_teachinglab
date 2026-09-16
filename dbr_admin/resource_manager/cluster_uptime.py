import logging
from datetime import datetime, timedelta, date
from ..database.db_operations import (
    ClusterUptime,
    ClusterCumulativeUptime,
    ClusterInfo,
    to_datetime
)

logging.basicConfig(level=logging.INFO)

def get_or_create_cluster_record(cluster_id: str) -> ClusterUptime:
    """
    Directly returns the Peewee record.
    If it doesn't exist (e.g., after midnight reset), it creates a new one.
    """
    record, created = ClusterUptime.get_or_create(
        cluster_id=cluster_id,
        defaults={
            'uptime_seconds': 0,
            'cumulative_seconds': 0,
            'start_time': None,
            'last_poll_time': None,
            'warning_sent': False,
            'force_terminated': False
        }
    )
    return record

def update_cumulative_uptime(cluster: dict):
    """
    Update the total uptime using a 'Delta-based' approach.

    This avoids the 'Absolute Time' bug where resetting the DB would
    incorrectly re-import uptime from before the reset.

      WHY NOT USE ABSOLUTE TIME (now - driver_start_time)?
    Using absolute time creates a dependency on the cluster's birth certificate.
    If this script's database is reset (e.g., at midnight), an absolute
    calculation would immediately 're-import' all uptime from the previous day
    because the cluster's start_timestamp hasn't changed.

    e.g.
    for each cluster_id, keep total uptime.

    on       -------       ------* <-- need to update this interval
    off -----       -------
    poll ^  ^  ^  ^  ^  ^  ^  ^  ^
    """
    assert 'driver' in cluster.keys()  # only running cluster is provided
    driver = cluster['driver']
    cluster_id = cluster['cluster_id']
    now = datetime.now()

    # 1. Retrieve current data (returns fresh record if DB was truncated)
    record = get_or_create_cluster_record(cluster_id)

    # 2. Parse driver start time
    driver_start_time = datetime.fromtimestamp(driver['start_timestamp'] / 1000)

    # 3. Handle Cluster Restart / New Record
    # Check if the cluster started more recently than our stored timestamp
    start_time_dt = to_datetime(record.start_time)
    is_restart = (start_time_dt is None or
                  abs((start_time_dt - driver_start_time).total_seconds()) > 1)

    if is_restart:
        logging.info(f"Cluster {cluster_id} restart/new record detected.")
        # Archive previous session's uptime to cumulative
        record.cumulative_seconds += record.uptime_seconds
        record.uptime_seconds = 0
        record.start_time= driver_start_time
        # Set bookmark to cluster start to catch the very first delta correctly
        record.last_poll_time = driver_start_time

    # 4. Calculate Delta (The "Relative" Logic)
    # If last_poll_timestamp is None (DB reset), we use 'now' as the reference
    # to avoid pulling in any time from before the reset.
    last_poll_time_dt = to_datetime(record.last_poll_time)
    reference_time = last_poll_time_dt or now

    # Calculate duration since last poll, ensuring we don't go before driver start
    effective_start = max(reference_time, driver_start_time)
    delta_seconds = (now - effective_start).total_seconds()

    # # Calculate time passed since the last poll, restricted by driver start
    # delta_seconds = max(0, now - max(reference_ts, driver_start_time))

    # 5. Update and Save directly to DB via ORM
    record.uptime_seconds += max(0.0,delta_seconds)
    record.last_poll_time = now
    record.save()

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
    daily_records = (
        ClusterCumulativeUptime
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
        query = (
            ClusterUptime
            .select(ClusterUptime, ClusterInfo)
            .join(ClusterInfo, on=(ClusterUptime.cluster_id == ClusterInfo.cluster_id))
            .order_by(ClusterUptime.cumulative_seconds.desc()))

        for record in query:
            # Calculate the full current uptime: accumulated + currently running
            cumulative_td = timedelta(seconds=record.cumulative_seconds + record.uptime_seconds)
            total_cumulative_uptime += cumulative_td
            report_lines.append(f"<li>Cluster {record.clusterinfo.cluster_name}: {format_timedelta_to_hhmm(cumulative_td)}</li>")

    report_lines.append(f"</ul><h2>Total Uptime Measured: {format_timedelta_to_hhmm(total_cumulative_uptime)}</h2>")
    return "\n".join(report_lines)
