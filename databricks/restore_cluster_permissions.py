"""
Verify all groups have CAN_RESTART permission in Azure DataBricks cluster
This is needed to restore normal operation after revoking permissions.
"""

import logging
import requests
from DataBricksClusterOps import DataBricksClusterOps

if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s  %(name)s  %(levelname)s  %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    from dotenv import load_dotenv
    import os

    load_dotenv()
    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')

    client = DataBricksClusterOps(host_='https://' + host, token_=token)
    x=client.get_clusters()
    for c in client.get_clusters():
        group_name = "g" + c['cluster_name'][8:]
        try:
            client.set_cluster_permission(c["cluster_id"], group_name=group_name, permission=client.ClusterPermission.RESTART)
            logger.info(f"Checked {c['cluster_id']}")
        except requests.HTTPError as e:
            logger.error(f"{e}, group {group_name}")

    logger.info('Exiting successfully')