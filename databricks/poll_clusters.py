"""

probably requires py version >= 3.10.2
https://www.itsupportwale.com/blog/how-to-upgrade-to-python-3-10-on-ubuntu-18-04-and-20-04-lts/

sudo apt install python3.10 python3.10-dev python3.10-venv
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

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
from DataBricksGroups import DataBricksGroups
from DataBricksClusterOps import DataBricksClusterOps
from resource_manager import cluster_uptime
from resource_manager.user_mail import send_emails


# {'members': [{'user_name': 'mdana@campus.technion.ac.il'}, {'user_name': 'liat.tsipory@campus.technion.ac.il'}]}
def get_emails_address(cluster_name: str, g:DataBricksGroups) -> list:
    """ The cluster name MUST be 'cluster_NNN'
    """
    addr = []
    for m in g.get_group_members("g" + cluster_name[8:]):
        addr.append(m['user_name'])
    return addr


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


def main():
    import pickle, datetime, os
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

    load_dotenv()
    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')
    if not host or not token:
        raise KeyError('DATABRICKS_HOST and/or DATABRICKS_TOKEN are missing')

    termination_watermark_minutes = float(os.getenv('DATABRICKS_MAX_UPTIME', 3*60+30))
    warning_watermark_minutes = float(os.getenv('DATABRICKS_WARN_UPTIME', 3*60))
    client = DataBricksClusterOps(host_='https://' + host, token_=token)
    dbr_groups = DataBricksGroups(host='https://' + host, token=token)
    check_running_clusters(client, uptime_db)

    clusters = client.get_clusters()

    # now that we have the updated times, run a check and act accordingly
    send_alert_threshold = datetime.timedelta(minutes=warning_watermark_minutes)
    terminate_cluster_threshold = datetime.timedelta(minutes=termination_watermark_minutes)
    # note: sending emails takes a lot of time, but we are not in a hurry --
    # expected to have very few messages.
    for cid,v in uptime_db.items():
        total_time = v.uptime + v.cumulative
        hours = total_time.seconds // 3600
        minutes = (total_time.seconds - hours * 3600) // 60
        cluster_name = cluster_id_to_cluster_name(clusters, cid)
        if (total_time > terminate_cluster_threshold) and not v.force_terminated:
            v.force_terminated = True
            logger.info(f"cluster {cluster_name} will be terminated NOW. It is up for {total_time}")

            send_emails(f"Your Cluster ({cluster_name})will be stopped now.",
                        body=f"Your cluster is used for too long during the last day.({hours}h{minutes}m , quota is {termination_watermark_minutes} minutes) and will be terminated soon. \n\n",
                        recipients = get_emails_address(cluster_name,dbr_groups),logger=logger)
            client.delete_cluster(cluster_name) # this will turn the cluster OFF, but not erase it.
            # prevent users from restarting the cluster
            group_name = "g" + cluster_name[8:]
            client.set_cluster_permission(cid,group_name=group_name, permission=client.ClusterPermission.ATTACH)

        elif (total_time > send_alert_threshold) and not v.warning_sent:
            v.warning_sent = True
            logger.info(f"cluster {cluster_name} time quota is almost used!  It is up for {total_time}")
            send_emails(f"Your Cluster  '{cluster_name}' time quota is almost used!",
                        body=f"""Your cluster is used for {hours}h{minutes}m during the last day.\n\
   It will be turned OFF when reaching {termination_watermark_minutes} minutes.\n\
   This message is sent at most once a day\n\
   The time quota is reset at midnight.\n\n""",
                        recipients=get_emails_address(cluster_name,dbr_groups),logger=logger)
        else:
            logger.debug(f"cluster {cluster_name} checked. It is up for {total_time}")

    with open('cluster_uptimes', 'wb') as outf:
        pickle.dump(uptime_db, outf)

    logger.info('Exiting successfully')


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print("Poll clusters crashed! email was sent")
        send_emails("Poll clusters crashed!", body= str(ex), recipients=['cnoam@technion.ac.il'], logger=None)
