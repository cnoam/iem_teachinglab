"""
Verify all groups have CAN_RESTART permission in Azure DataBricks cluster
This is needed to restore normal operation after revoking permissions.
"""

import requests
from DataBricksClusterOps import DataBricksClusterOps

def restore_cluster_permissions(host,token,logger):

    client = DataBricksClusterOps(host_='https://' + host, token_=token)
    x=client.get_clusters()
    for c in client.get_clusters():
        group_name = "group_" + c['cluster_name'][8:]
        try:
            client.set_cluster_permission(c["cluster_id"], group_name=group_name, permission=client.ClusterPermission.RESTART)
            logger.info(f"Checked {c['cluster_id']}")
        except requests.HTTPError as e:
            logger.error(f"{e}, group {group_name}")

    logger.info('restore_cluster_permissions completed')