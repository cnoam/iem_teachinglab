import json
import logging
from enum import Enum
import requests
from databricks_cli.clusters.api import ClusterApi
from databricks_cli.dbfs.api import DbfsApi
from databricks_cli.dbfs.dbfs_path import DbfsPath
from databricks_cli.sdk.api_client import ApiClient

from DataBricksGroups import DataBricksGroups

dry_run = False

class DataBricksClusterOps:
    """
    Use Databricks API to administer a cluster.

    * create a cluster
    * delete c cluster
    * get list of clusters

    https://docs.databricks.com/dev-tools/python-api.html

    This class uses API 2.0 (legacy)

    To generate a token
    https://docs.databricks.com/dev-tools/auth.html#pat
    """

    class ClusterPermission(Enum):
        MANAGE = 1
        RESTART = 2
        ATTACH = 3

    def __init__(self, host_: str, token_: str):
        self.api_client = ApiClient(host=host_, token=token_)
        self.token = token_
        self.host = host_
        self.cached_clusters = None

    def get_clusters(self):
        """ get the list of currently defined clusters (both online and offline)
        :return list( dict( cluster parameters))
        """
        if self.cached_clusters is not None:
            return self.cached_clusters

        clusters_api = ClusterApi(self.api_client)
        clusters_list = clusters_api.list_clusters()
        try:
            self.cached_clusters = clusters_list['clusters']
        except KeyError:
            return []
        return self.cached_clusters

    def print_clusters(self):
        """ will print something like
        Cluster name, cluster ID
        Noam Cohen's Shared Compute Cluster, 0101-113520-xpnpa7h0
        Noam Cohen's Cluster, 1227-092825-t38f2uc4
        """
        print("Cluster name, cluster ID")
        for cluster in self.get_clusters():
            print(f"{cluster['cluster_name']}, {cluster['cluster_id']}")

    def download_file_dbfs(self, dbfs_source_file_path):
        """
        NOT TESTED
        Download a file
        :param dbfs_source_file_path: 'dbfs:/tmp/users/someone@example.com//hello-world.txt'
        """
        dbfs_path = DbfsPath(dbfs_source_file_path)
        local_file_download_path = '.' + dbfs_source_file_path[dbfs_source_file_path.rfind('/')]
        # Download the workspace file locally.
        DbfsApi(self.api_client).get_file(dbfs_path, local_file_download_path, overwrite=True)

    def create_cluster_from_spec(self, json_spec: dict):
        """
        Create a new cluster
        :param json_spec:  json doc that defines the cluster
        """
        new_cluster = ClusterApi(self.api_client).create_cluster(json_spec)
        if new_cluster:
            self.cached_clusters = None
        return new_cluster

    def create_cluster(self, name: str, policy_id: str):
        """
        Create a cluster in this host based on one specific template.
        This is a helper method.
        Change the template to your liking.
        Cluster name are not unique in Databricks workspace, so I add enforcing here name uniqueness
        :raise AttributeError
        :return HttpResponse
        """

        if name in set([c['cluster_name'] for c in self.get_clusters()]):
            raise AttributeError(f'cluster {name} already exists. Refusing to create another one')

        from string import Template
        import json
        # good luck using f"..." with json docs.
        template = Template("""{
              "autoscale": {
                  "min_workers": 1,
                  "max_workers": 3
              },
              "cluster_name": "$cluster_name",
              "spark_version": "14.3.x-scala2.12",
              "spark_conf": {
                  "spark.databricks.delta.preview.enabled": "true"
              },
              "azure_attributes": {
                  "first_on_demand": 1,
                  "availability": "ON_DEMAND_AZURE",
                  "spot_bid_max_price": -1
              },
              "node_type_id": "Standard_DS3_v2",
              "driver_node_type_id": "Standard_DS3_v2",
              "ssh_public_keys": [],
              "custom_tags": {},
              "cluster_log_conf": {
                  "dbfs": {
                    "destination": "dbfs:/cluster-logs"
                  }
              },
              "spark_env_vars": {"PYSPARK_PYTHON": "/databricks/python3/bin/python3"},
              "autotermination_minutes": 14,
              "enable_elastic_disk": true,
              "cluster_source": "UI",
              "init_scripts": [],
              "data_security_mode": "NONE",
              "runtime_engine": "STANDARD"
        }""")
        tmp = template.substitute(cluster_name=name, policy_id=policy_id)
        json_spec = json.loads(tmp)
        return self.create_cluster_from_spec(json_spec)

    def cluster_from_name(self, name: str):
        clusters = self.get_clusters()
        r = list(filter(lambda c: c['cluster_name'] == name, clusters))
        if len(r) == 0:
            raise KeyError(f'{name} not found in the list of clusters')
        if len(r) > 1:
            raise KeyError(f'There are multiple clusters with name:{name}.')
        return r[0]

    def delete_cluster(self, name):
        """Terminate a cluster, but do not delete it.
        The name is misleading because this is how the API works
        :return: None
        :raise KeyError if name not found or not unique
        """
        global dry_run
        if dry_run:
            print(f"FAKE: delete cluster {name}")
            return
        r = self.cluster_from_name(name)
        ClusterApi(self.api_client).delete_cluster(cluster_id=r['cluster_id'])

    def permanent_delete_cluster(self, cluster_id: str, verbose: bool = False):
        if verbose:
            print(f"permanent delete cluster {cluster_id}")
        ClusterApi(self.api_client).permanent_delete(cluster_id=cluster_id)

    def permanent_delete_all_clusters(self, verbose: bool = False, unsafe: bool = False):
        """Delete forever all the clusters in this workspace"""
        if not unsafe:
            ok = input("About to permanently delete ALL CLUSTERS. If this is ok, type 'yes': ")
            if ok != 'yes':
                print("Cancelled.")
                return
        clusters = self.get_clusters()
        for cluster in clusters:
            self.permanent_delete_cluster(cluster['cluster_id'], verbose)

    def edit_cluster_permissions(self, cluster_id, config: dict) -> None:
        """
        Edit access permissions for a cluster.
        see    https://redocly.github.io/redoc/?url=https://learn.microsoft.com/azure/databricks/_extras/api-refs/permissions-2.0-azure.yaml

        :param: config - dict: configuration to apply to the cluster
                Exactly 1 of virtual_cluster_size, num_workers or autoscale must be specified
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f'{self.host}/api/2.0/permissions/clusters/{cluster_id}'
        response = requests.api.put(url=url, headers=headers, data=json.dumps(config))
        response.raise_for_status()

    def set_cluster_permission(self, cluster_id: str, group_name: str, permission: ClusterPermission) -> None:
        if permission == self.ClusterPermission.ATTACH:
            s = "CAN_ATTACH_TO"
        elif permission == self.ClusterPermission.RESTART:
            s = "CAN_RESTART"
        elif permission == self.ClusterPermission.MANAGE:
            s = "CAN_MANAGE"
        else:
            raise ValueError('impossible permission')
        config = {"access_control_list": [{"group_name": group_name, "permission_level": s}]}
        self.edit_cluster_permissions(cluster_id, config)

    def attach_groups_to_clusters(self, groups: list, verbose: bool = False) -> None:
        """
        For each group (in the format gNUMBER), attach it to a cluster with the name cluster_NUMBER
        :param: groups . list of group names.
        """
        for gname in groups:
            gid = int(gname[1:])
            cluster_name = f"cluster_{gid}"
            if verbose:
                print(f"attaching group {gid} to {cluster_name}")
                try:
                    self.set_cluster_permission(self.cluster_from_name(cluster_name)['cluster_id'], gname, self.ClusterPermission.RESTART)
                except requests.exceptions.HTTPError as ex:
                    if ex.response.status_code == 404:
                        logging.error(f"Attaching group {gid} to {cluster_name} Failed: group not found.")

    def install_libraries(self, cluster_id: str, libraries: list[dict]) -> requests.Response:
        """
        Install libraries on a cluster
        :param cluster_id: the cluster to install the libraries on
        :param libraries: list of libraries to install. The list is in the format specified in the API docs
        https://docs.databricks.com/api/workspace/libraries/install
        """
        """
        {
          "cluster_id": "string",
          "libraries": [
            {
              "jar": "string",
              "egg": "string",
              "pypi": {
                "package": "string",
                "repo": "string"
              },
              "maven": {
                "coordinates": "string",
                "repo": "string",
                "exclusions": [
                  "string"
                ]
              },
              "cran": {
                "package": "string",
                "repo": "string"
              },
              "whl": "string"
            }
          ]
        }
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f'{self.host}/api/2.0/libraries/install'
        data = json.dumps({"cluster_id": cluster_id, "libraries": libraries})
        return requests.api.post(url=url, headers=headers, data=data)

    def update_configuration(self, cluster: dict, config: dict) -> requests.Response:
        """
        Update the configuration of a cluster
        :param cluster: the cluster to update. A dictionary containing the cluster's details as returned by the API
        :param config: the new configuration using the json format specified in the API docs

        see https://docs.databricks.com/api/azure/workspace/clusters/edit for the format of the config

        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f'{self.host}/api/2.0/clusters/edit'
        data = json.dumps(config)
        return requests.api.post(url=url, headers=headers, data=data)

    def update_auto_termination(self, cluster: dict, minutes: int) -> requests.Response:
        """
        Update the auto-termination time of a cluster
        :param cluster: the cluster to update
        :param minutes: the new auto-termination time in minutes

        The doc at https://docs.databricks.com/api/azure/workspace/clusters/edit is wrong. both autoscale and node_type_id are mandatory
        """

        if cluster['autotermination_minutes'] == minutes:
            res = requests.Response() # make it look like a successful response
            res.status_code = 200
            return res
        if 'autoscale' not in cluster:
            #raise ValueError("Cluster must have autoscale field")
            res = requests.Response()
            res.status_code = 400
            return res
        new_config = {'cluster_id': cluster['cluster_id'],
                      'cluster_name': cluster['cluster_name'],
                      'spark_version': cluster['spark_version'],
                      'autoscale': cluster['autoscale'],
                      'node_type_id': cluster['node_type_id'],
                      # all the above are mandatory
                      'autotermination_minutes': minutes,
                      }

        # note: originaly I did
        # new_config = cluster
        # update needed fields
        # but it didn't work because the original cluster has more fields than the ones that are allowed to be updated
        return self.update_configuration(cluster, new_config)

    def pin_cluster(self, cluster: dict):
        """Pin a cluster, so it will not be auto-deleted from the workspace"""
        _data = {}
        cluster_id = cluster['cluster_id']
        if cluster_id is not None:
            _data['cluster_id'] = cluster_id
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f'{self.host}/api/2.0/clusters/pin'
        response = requests.post(url,json.dumps(_data), headers=headers)
        response.raise_for_status()
