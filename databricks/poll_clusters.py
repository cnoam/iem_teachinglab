"""
This script is called periodically (e.g. by cron).
It checks if any of the running Databricks clusters exceeded total uptime.

If uptime > hard-thr: turn off the cluster
if uptime > soft-thr: send message to user

To reset the total uptime, you would run a dedicated job (like the
log_daily_uptime function) that resets the `uptime_seconds` field.
The database file itself (cluster_uptimes.db) persists across runs.
"""
import json
import logging, os
import datetime
from DataBricksGroups import DataBricksGroups
from DataBricksClusterOps import DataBricksClusterOps
from main import group_name_int, check_mandatory_env_vars

from resource_manager.cluster_uptime import (
    update_cumulative_uptime,
    get_or_create_cluster_data,
    save_cluster_data
)
from databricks.database.db_operations import ClusterUptime
from resource_manager.user_mail import send_emails


# {'members': [{'user_name': 'mdana@campus.technion.ac.il'}, {'user_name': 'liat.tsipory@campus.technion.ac.il'}]}
def get_emails_address(cluster_name: str, g: DataBricksGroups) -> list:
    """ The cluster name MUST be 'cluster_NNN'
    """
    import re
    assert re.match(r"cluster_\d{1,3}$", cluster_name)

    addr = []
    for m in g.get_group_members(group_name_int(int(cluster_name[8:]))):
        addr.append(m['user_name'])
    return addr


def check_update_running_clusters(client, clusters : list[dict]):
    """
    Checks running clusters and updates 'ClusterUptime' model records.
    The database connection is handled globally/via context manager.
    :param client: Databricks client
    :param clusters: list of clusters. Each cluster is a dict
    """
    for c in clusters:
        if 'driver' in c.keys():
            update_cumulative_uptime(c)


def cluster_id_to_cluster_name(clusters: list[dict], id_: str) -> str | None:
    clustersmatching = list(filter(lambda t: t['cluster_id'] == id_, clusters))
    if len(clustersmatching) == 0:
        return None
    return clustersmatching[0]['cluster_name']

def dump_cluster_uptime_db():

    for record in ClusterUptime.select():
        print(f"ID: {record.id}, Cumulative Sec: {record.cumulative_seconds}, Uptime Sec: {record.uptime_seconds}")

def main():

    #  Check that the caller properly opened the connection.
    #assert db_instance._state.conn, "Database must be connected when calling main(db_instance)"

    #dump_cluster_uptime_db()
    logger = logging.getLogger('CLUSTER_POLL')
    # Check if handlers exist before adding a new one.
    # This prevents duplicate logs when main() is called multiple times (e.g. in tests).
    if not logger.handlers:
        logger.propagate = False # so the root handler will not duplicate logs
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s  %(name)s  %(levelname)s  %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    logger.info('Checking clusters...')
    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')

    termination_watermark_minutes = float(os.getenv('DATABRICKS_MAX_UPTIME', 3 * 60 + 30))
    warning_watermark_minutes = float(os.getenv('DATABRICKS_WARN_UPTIME', 3 * 60))
    client = DataBricksClusterOps(host_='https://' + host, token_=token)
    dbr_groups = DataBricksGroups(host='https://' + host, token=token)


    clusters = client.get_clusters()
    json.dump(clusters, open('clusters.json', 'w'), indent=2)
    check_update_running_clusters(client, clusters)

    # now that we have the updated times, run a check and act accordingly
    send_alert_threshold = datetime.timedelta(minutes=warning_watermark_minutes)
    terminate_cluster_threshold = datetime.timedelta(minutes=termination_watermark_minutes)
    # note: sending emails takes a lot of time, but we are not in a hurry --
    # expected to have very few messages.
    # Iterate directly over Peewee model records instead of dictionary
    # Select all records from the ClusterUptime model

    # Inside the loop below, we change the DB contents, so the iterator
    # in select() gets confused.
    # Classic solution is to create a copy
    all_records = list(ClusterUptime.select())
    for record in all_records:
        # 1. Re-hydrate the ClusterData object from the DB record
        # We use the helper function to convert seconds back to timedelta/bool
        v = get_or_create_cluster_data(record.id)

        # 2. Threshold Check Logic (largely unchanged, but using Peewee object)
        total_time = v.uptime + v.cumulative
        hours = total_time.total_seconds() // 3600  # MODIFIED: Use .total_seconds() for timedelta
        minutes = (total_time.total_seconds() - hours * 3600) // 60  # MODIFIED: Use .total_seconds()

        cluster_name = cluster_id_to_cluster_name(clusters, record.id)
        cid = record.id

        if not cluster_name:
            logger.error(f'Cluster name not found {cid}. This is an error! Skipping.')
            continue

        # --- TERMINATION CHECK ---
        if (total_time > terminate_cluster_threshold) and not v.force_terminated:
            # Update the object, then save back to DB
            v.force_terminated = True
            save_cluster_data(cid, v)

            logger.info(f"cluster {cluster_name} will be terminated NOW. It is up for {total_time}")

            send_emails(f"Your Cluster '{cluster_name}' will be stopped now.",
                        body=f"Your cluster is used for too long during the last day.({int(hours)}h{int(minutes)}m , quota is {termination_watermark_minutes} minutes) and will be terminated soon. \n\n",
                        recipients=get_emails_address(cluster_name, dbr_groups), logger=logger)
            client.delete_cluster(cluster_name)  # this will turn the cluster OFF, but not erase it.

            # prevent users from restarting the cluster
            cname_id = int(cluster_name[8:])
            client.set_cluster_permission(cid, group_name=group_name_int(cname_id),
                                          permission=client.ClusterPermission.ATTACH)

        # --- WARNING CHECK ---
        elif (total_time > send_alert_threshold) and not v.warning_sent:
            v.warning_sent = True
            save_cluster_data(cid, v)

            logger.info(f"cluster {cluster_name} time quota is almost used! It is up for {total_time}")
            send_emails(subject=f"Your Cluster  '{cluster_name}' is working for a long time",
                        body=f"""Your cluster is used for {int(hours)}h{int(minutes)}m during the last day.\n\
Please check if you still need it!\n \
This message is sent at most once a day\n\
The time quota is reset at midnight.\n\n""",

                        recipients=get_emails_address(cluster_name, dbr_groups), logger=logger)
        else:
            logger.debug(f"cluster {cluster_name} checked. It is up for {int(hours)}h {int(minutes):02d}m")

    logger.info('Exiting successfully')


def text_to_pre_html(text: str) -> str:
    # Use a <pre> tag to preserve whitespace and newlines
    return f"<pre>{text}</pre>"


if __name__ == "__main__":
    import traceback

    from dotenv import load_dotenv
    import os

    load_dotenv()
    check_mandatory_env_vars()

    #  We must ensure the DB connection is open and the tables exist
    # when running directly. In a production environment, you would ensure the
    # tables are created once at deployment.
    try:
        # NOTE: Assumes a create_tables function exists in db_operations
        from databricks.database.db_operations import create_tables, initialize_production_db
        # Initialize the production database before creating tables
        prod_db = initialize_production_db()
        with prod_db.connection_context():
            create_tables(prod_db)
            main()
    except Exception as ex:
        print("Poll clusters crashed! email was sent")
        trace = traceback.format_exc()
        send_emails("Poll clusters crashed!", body=text_to_pre_html(f"{str(ex)}\n\n{trace}"),
                    recipients=[os.getenv('ADMIN_EMAIL')], logger=None)



        # ---------- 2025-11-18 the format returned from DBR API for each cluster
        """{'autoscale': {'max_workers': 4, 'min_workers': 1, 'target_workers': 1}, 'autotermination_minutes': 20, 'azure_attributes': {'availability': 'ON_DEMAND_AZURE', 'first_on_demand': 1, 'spot_bid_max_price': -1.0}, 'cluster_id': '0425-171142-ryp39emt', 'cluster_log_conf': {'dbfs': {'destination': 'dbfs:/cluster-logs'}}, 'cluster_log_status': {'last_attempted': 1754767298325}, 'cluster_name': 'cluster_01', 'cluster_source': 'UI', 'creator_user_name': 'cnoam@technion.ac.il', 'custom_tags': {'origin': 'terraform'}, 'data_security_mode': 'NONE', 'default_tags': {'ClusterId': '0425-171142-ryp39emt', 'ClusterName': 'cluster_01', 'CreatedBy': 'Noam Cohen', 'Creator': 'cnoam@technion.ac.il', 'ManagedBy': 'Terraform ONLY!!', 'Vendor': 'Databricks'}, 'disk_spec': {}, 'driver_healthy': True, 'driver_instance_source': {'node_type_id': 'Standard_DS3_v2'}, 'driver_node_type_id': 'Standard_DS3_v2', 'effective_spark_version': '15.4.x-cpu-ml-scala2.12', 'enable_elastic_disk': True, 'enable_local_disk_encryption': False, 'init_scripts_safe_mode': False, 'instance_source': {'node_type_id': 'Standard_DS3_v2'}, 'last_activity_time': 1754765587101, 'last_restarted_time': 1754765528390, 'last_state_loss_time': 1754765528313, 'node_type_id': 'Standard_DS3_v2', 'pinned_by_user_name': '6662685270297676', 'release_version': '15.4.21', 'runtime_engine': 'STANDARD', 'spark_context_id': 622824693634383465, 'spark_env_vars': {'PYSPARK_PYTHON': '/databricks/python3/bin/python3'}, 'spark_version': '15.4.x-cpu-ml-scala2.12', 'start_time': 1745601102611, 'state': 'TERMINATED', 'state_message': 'Inactive cluster terminated (inactive for 20 minutes).', 'terminated_time': 1754767635889, 'termination_reason': {'code': 'INACTIVITY', 'parameters': {'inactivity_duration_min': '20'}, 'type': 'SUCCESS'}}"""