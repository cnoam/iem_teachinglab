import logging
from datetime import datetime, timedelta
from pyrecord import Record

ClusterData = Record.create_type("ClusterData", "start_time", "uptime", "cumulative", "warning_sent")

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
        db[id] = ClusterData(timedelta(hours= 0),timedelta(hours= 0),timedelta(hours= 0),warning_sent=False)
    start_time = datetime.fromtimestamp(driver['start_timestamp'] / 1000)
    uptime = datetime.now() - start_time
    if db[id].start_time != start_time:
        # cluster is newly turned on
        logging.info(f"Cluster {id} is turned on again")
        db[id].cumulative += db[id].uptime
        db[id].start_time = start_time
    db[id].uptime = uptime  # replace the previous value
