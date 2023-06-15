"""
This script is called periodically (e.g. by cron).
It checks if any of the running Databricks clusters exceeded total uptime.

If uptime > hard-thr: turn off the cluster
if uptime > soft-thr: send message to user

To reset the total uptime, simply delete the file "cluster_uptimes" . This can be done directly from crontab without code
in crontab (use crontab -e as the user who owns the script):

# run every midnight
0 0 * * * unlink /home/USERNAME/path/to/cluster_uptimes

# run every 10 minutes
*/10 * * * * python /home/USERNAME/path/to/poll_cluster.py
"""


import logging
from DataBricksClusterOps import DataBricksClusterOps
from resource_manager import cluster_uptime
from resource_manager.user_mail import send_emails, get_emails_address

def check_running_clusters(client, uptime_db:dict):
    """check and update 'uptime_db'
    """
    clusters = client.get_clusters()
    for c in clusters:
        if 'driver' in c.keys():
            cluster_uptime.update_cumulative_uptime(c, uptime_db)

def cluster_id_to_cluster_name(clusters, id:int)->str:
    cluster = list(filter(lambda t: t['cluster_id'] == id, clusters))[0]
    return cluster['cluster_name']


if __name__ == "__main__":
    import pickle, datetime
    logger = logging.getLogger('CLUSTER_POLL')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s  %(name)s  %(levelname)s  %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.info('Checking clusters...')

    try:
        with open('cluster_uptimes','rb') as datafile:
            uptime_db = pickle.load(datafile)
    except FileNotFoundError:
        uptime_db = {}

    from dotenv import load_dotenv
    import os

    load_dotenv()
    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')
    termination_watermark_minutes = os.getenv('DATABRICKS_MAX_UPTIME', 180)
    warning_watermark_minutes = os.getenv('DATABRICKS_WARN_UPTIME', 120)
    client = DataBricksClusterOps(host='https://' + host, token=token)

    check_running_clusters(client, uptime_db)

    clusters = client.get_clusters()
    with open('cluster_uptimes', 'wb') as datafile:
        pickle.dump(uptime_db, datafile)

    # now that we have the updated times, run a check and act accordingly
    send_alert_threshold = datetime.timedelta(minutes=warning_watermark_minutes)
    terminate_cluster_threshold = datetime.timedelta(minutes=termination_watermark_minutes)
    # note: sending emails takes a lot of time, but we are not in a hurry --
    # expected to have very few messages.
    for cid,v in uptime_db.items():
        total_time = v.uptime + v.cumulative
        cluster_name = cluster_id_to_cluster_name(clusters, cid)
        if total_time > terminate_cluster_threshold:
            logger.info(f"cluster {cid} will be terminated NOW. It is up for {total_time}")
            send_emails("Your Cluster will be stopped now.",
                        body="Your cluster is used for too long during the last day",
                        recipients = get_emails_address(cluster_name))
            client.delete_cluster(cluster_name) # this will turn the cluster OFF, but not erase it.

        elif total_time > send_alert_threshold:
            logger.info(f"cluster {cid} will be terminated soon. It is up for {total_time}")
            send_emails("Your Cluster is running too long!", body= f"Your cluster is used for {total_time} during the last day.\n It will be turned OFF when reaching {terminate_cluster_threshold}",
                        recipients=get_emails_address(cluster_name))
        else:
            logger.debug(f"cluster {cid} checked. It is up for {total_time}")
    logger.info('Exiting successfully')