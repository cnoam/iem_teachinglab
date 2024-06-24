import logging
from datetime import datetime, timedelta
from pyrecord import Record

ClusterData = Record.create_type("ClusterData", "start_time", "uptime", "cumulative", "warning_sent","force_terminated")
from databricks.database.db_operations import DB
logging.basicConfig(level=logging.INFO)


def update_cumulative_uptime(cluster: dict, db :DB):
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
        db.insert_uptime(id, ClusterData(timedelta(hours= 0),timedelta(hours= 0),timedelta(hours= 0),warning_sent=False, force_terminated=False))

    start_time = datetime.fromtimestamp(driver['start_timestamp'] / 1000)
    uptime = datetime.now() - start_time
    x = ClusterData(*db[id])
    if x.start_time != start_time:
        # cluster is newly turned on
        logging.info(f"Cluster {id} is turned on again")
        x.cumulative += x.uptime
        x.start_time = start_time
    x.uptime = uptime  # replace the previous value
    db.update_record(id, x)
"""
# Retrieve data from the table
cursor.execute("SELECT uptime FROM cluster_uptimes WHERE id = '1'")
result = cursor.fetchone()
if result:
    uptime_str = result[0]  # Get the uptime as a string
    uptime_obj = datetime.datetime.strptime(uptime_str, '%H:%M:%S').time()  # Parse the string to a datetime.time object
    print("Uptime:", uptime_obj)
    
"""



def create_usage_report()-> str:
	raise Exception("not impl")
