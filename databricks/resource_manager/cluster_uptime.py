import logging
from datetime import datetime, timedelta
from pyrecord import Record

ClusterData = Record.create_type("ClusterData", "start_time", "uptime", "cumulative", "warning_sent","force_terminated")

def update_cumulative_uptime(cluster: dict, db):
    """
    update the total uptime of resource in our DB.
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
    if id not in db:
        # first time we see this cluster since it was started running (since it was offline)
        db[id] = ClusterData(timedelta(hours= 0),timedelta(hours= 0),timedelta(hours= 0),warning_sent=False, force_terminated=False)
    start_time = datetime.fromtimestamp(driver['start_timestamp'] / 1000)
    uptime = datetime.now() - start_time
    if db[id].start_time != start_time:
        # cluster is newly turned on
        logging.info(f"Cluster {id} is turned on again")
        db[id].cumulative += db[id].uptime
        db[id].start_time = start_time
    db[id].uptime = uptime  # replace the previous value


def create_usage_report()-> str:
    """Create a report in HTML showing the main usage of the clusters."""
    import pprint, pickle

    try:
        with open('../cluster_uptimes','rb') as datafile:
            uptime_db = pickle.load(datafile)
    except FileNotFoundError:
        uptime_db = {}


    # Generate HTML
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cluster Usage Data</title>
        <style>
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            tfoot {{
                font-weight: bold;
                background-color: #f9f9f9;
        }}
        </style>
    </head>
<body>
    <h1>Cluster Usage Data</h1> 
    <h2>Date: {today_date}</h2>
    <table>
        <thead>
            <tr>
                <th>Uptime</th>
                <th>Warning Sent</th>
                <th>Force Terminated</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
        <tfoot>
            <tr>
                <td>Total Time: {total_time}</td>
                <td colspan="2"></td>
            </tr>
        </tfoot>
    </table>
</body>
    </html>
    """

    # Generate table rows
    rows = ""
    total_uptime = timedelta()
    sorted_data = sorted(uptime_db.items(), key=lambda item: item[1].uptime, reverse=True)
    for cluster_id, cluster in sorted_data:
        uptime_formatted = str(cluster.uptime).split('.')[0]  # Format uptime as HH:MM:SS
        warning_sent = "Yes" if cluster.warning_sent else "No"
        force_terminated = "Yes" if cluster.force_terminated else "No"
        rows += f"<tr><td>{uptime_formatted}</td><td>{warning_sent}</td><td>{force_terminated}</td></tr>\n"
        total_uptime += cluster.uptime
    total_uptime_formatted = str(total_uptime).split('.')[0]
    # Complete the HTML
    today_date = datetime.now().strftime("%Y-%m-%d")
    html_content = html_template.format(rows=rows, total_time=total_uptime_formatted, today_date=today_date)
    return html_content

if __name__ == '__main__':
    with open("cluster_data.html", "w") as file:
        file.write(create_usage_report())

