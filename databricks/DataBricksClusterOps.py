import json
from enum import Enum
import requests
from databricks_cli.sdk.api_client import ApiClient
from databricks_cli.clusters.api import ClusterApi
from databricks_cli.dbfs.api import DbfsApi
from databricks_cli.dbfs.dbfs_path import DbfsPath


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


    def __init__(self,host:str, token:str):
        self.api_client = ApiClient(host=host,token=token)
        self.token = token
        self.host = host
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
        :param api_client: instance of ApiClient
        :param dbfs_source_file_path: 'dbfs:/tmp/users/someone@example.com//hello-world.txt'
        """
        dbfs_path = DbfsPath(dbfs_source_file_path)
        local_file_download_path = '.' + dbfs_source_file_path[dbfs_source_file_path.rfind('/')]
        # Download the workspace file locally.
        DbfsApi(self.api_client).get_file(dbfs_path, local_file_download_path, overwrite=True)

    def create_cluster_from_spec(self, json_spec: dict):
        """
        Create a new cluster
        :param api_client:
        :param json_spec:  json doc that defines the cluster
        """
        return ClusterApi(self.api_client).create_cluster(json_spec)

    def create_cluster(self, name: str, policy_id:str):
        """
        Create a cluster in this host based on one specific template.
        This is a helper method.
        Change the template to your liking.
        Cluster name are not unique in Databricks workspace, so I add enforcing here name uniqness
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
                  "max_workers": 1
              },
              "cluster_name": "$cluster_name",
              "spark_version": "11.3.x-scala2.12",
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
              "spark_env_vars": {},
              "autotermination_minutes": 10,
              "enable_elastic_disk": true,
              "cluster_source": "UI",
              "init_scripts": [],
              "policy_id": "$policy_id",
              "data_security_mode": "NONE",
              "runtime_engine": "STANDARD"
        }""")
        tmp = template.substitute(cluster_name=name, policy_id=policy_id)
        json_spec = json.loads(tmp)
        return self.create_cluster_from_spec(json_spec)

    def cluster_from_name(self, name:str):
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

        r = self.cluster_from_name(name)
        ClusterApi(self.api_client).delete_cluster(cluster_id=r['cluster_id'])

    def permanent_delete_cluster(self, cluster_id:str, verbose:bool=False):
        if verbose:
            print(f"permanent delete cluster {cluster_id}")
        ClusterApi(self.api_client).permanent_delete(cluster_id=cluster_id)

    def permanent_delete_all_clusters(self,verbose:bool=False, unsafe:bool=False):
        """Delete forever all the clusters in this workspace"""
        if not unsafe:
            ok = input("About to permanently delete ALL CLUSTERS. If this is ok, type 'yes': ")
            if ok != 'yes':
                print("Cancelled.")
                return
        clusters = self.get_clusters()
        for cluster in clusters:
            self.permanent_delete_cluster(cluster['cluster_id'],verbose)

    def edit_cluster_permissions(self, cluster_id, config:dict) -> None:
        """
        Edit access permissions for a cluster.
        see    https://redocly.github.io/redoc/?url=https://learn.microsoft.com/azure/databricks/_extras/api-refs/permissions-2.0-azure.yaml

        :param: config - dict: configuration to apply to the cluster
                Exactly 1 of virtual_cluster_size, num_workers or autoscale must be specified
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f'{self.host}/api/2.0/permissions/clusters/{cluster_id}'
        response = requests.api.patch(url=url, headers=headers, data=json.dumps(config))
        response.raise_for_status()

    def set_cluster_permission(self,cluster_id:str, group_name:str, permission: ClusterPermission )-> None:
        if permission == self.ClusterPermission.ATTACH:
            s = "CAN_ATTACH_TO"
        elif permission == self.ClusterPermission.RESTART:
            s = "CAN_RESTART"
        elif permission == self.ClusterPermission.MANAGE:
            s = "CAN_MANAGE"
        else:
            raise ValueError('impossible permission')
        config = { "access_control_list": [ {"group_name":group_name, "permission_level": s}]}
        self.edit_cluster_permissions(cluster_id,config)

    def attach_groups_to_clusters(self, groups:list, verbose:bool=False )-> None:
        """
        For each group (in the format gNUMBER), attach it to a cluster with the name cluster_NUMBER
        :param: groups . list of group names.
        """
        for gname in groups:
            gid = int(gname[1:])
            cluster_name = f"cluster_{gid}"
            if verbose:
                print( f"attaching group {gid} to {cluster_name}")
            self.set_cluster_permission(self.cluster_from_name(cluster_name)['cluster_id'],gname, self.ClusterPermission.RESTART)

    def create_group(self,group_name: str):
        """
        :param group_name:
        :return: the http response
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f'{self.host}/api/2.0/groups/create'
        data = '{ "group_name": "%s" }' % group_name
        return requests.api.post(url=url, headers=headers, data=data)

    def add_member_to_group(self, member_name: str, group_name: str, is_user: bool):
        """
        Add a databricks user to a group.
        Both user and group MUST exist.
        :param member_name     user or group name to add
        :param group_name the parent group (where we want to add the member)
        :param is_user True if adding a user, False if adding a group
        :return: the http response
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f'{self.host}/api/2.0/groups/add-member'
        attr = 'user_name' if is_user else 'group_name'
        data = '{ "%s": "%s", "parent_name": "%s" }' % (attr, member_name, group_name)
        return requests.api.post(url=url, headers=headers, data=data)

    def create_users(self,users: list):
        """
        Add users to Databricks workspace.
        If a user is already added, the cluster will return 409 and will not add the user again.

        :param users: list(string of user's email)
        :return: number of successfully added users
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f'{self.host}/api/2.0/preview/scim/v2/Users'
        num_ok = 0
        for user in users:
            if len(user) == 0:
                continue
            data = """{{"schemas":["urn:ietf:params:scim:schemas:core:2.0:User"],"userName":"{user}"}}""".format(user=user)
            response = requests.api.post(url=url, headers=headers, data=data)
            if response:  # this format of checking will cover also 201, 304 etc.
                num_ok += 1
        return num_ok


def create_users_from_moodle(dbapi: DataBricksClusterOps, filename:str, verbose:bool) -> int :
    """
    Read Moodle user groups, and create Databricks groups with these users
    The groups and users MUST NOT exist before in Databricks workspace.

    :param dbapi: initialized connection to Databricks API
    :param filename: CSV file in Moodle format, group assignment
    :return: number of groups created in the workspace
    :raise HTTPstatus if any of the requests failed
    """
    from MoodleFileParser import MoodleFileParser
    groups = MoodleFileParser.parse_moodle_csv(filename)

    # create a master group that contains all the groups. This will make it
    # easy for the admin to give access.
    master_group_name = "all_student_groups"
    response = dbapi.create_group(master_group_name)
    response.raise_for_status()

    for group, users in groups.items():
        # the 'users' is full email address, all in the same domain.
        # let's remove the domain -- we know that the name will be unique in a single domain.
        #shortnames = [u[: u.rfind('@')]  for u in users]
        group_name = "g" + str(group)
        response = dbapi.create_group(group_name)
        response.raise_for_status()

        # Add the newly created group to the "master group"
        response = dbapi.add_member_to_group(group_name,master_group_name, is_user=False)
        response.raise_for_status()

        nCreated = dbapi.create_users(users)
        if nCreated != len(users):
            print(f"Warning: at least one of {users} was not created")
        for u in users:
            response = dbapi.add_member_to_group(u, group_name, is_user=True)
            response.raise_for_status()

        if verbose:
            print(f"{group}",end=' ')
    if verbose:
        print('\n')
    return len(groups)


def test_user_creation_from_moodle(client):
    create_users_from_moodle(client, '/home/cnoam/Desktop/94290w2022.csv')


def create_clusters(how_many:int, verbose:bool = False):
    for i in range(how_many):
        resp1 = client.create_cluster( f"cluster_{i}", policy_id=policy_id) # create the cluster and turn it ON
        if resp1:
            client.delete_cluster(f"cluster_{i}")  # turn the cluster OFF. We don't want to run it now.
        else:
            print(f"Failed created cluster {i}")
        if verbose:
            print(f"cluster {i}",end=' ')
    if verbose:
        print('\n')


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    import sys,os
    x = sys.argv
    if len(sys.argv) != 2:
        print("Usage: prog groups_in_moodle.csv")
        exit(1)

    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')
    policy_id=os.getenv('POLICY_ID')
    if host is None or token is None:
        raise RuntimeError('must set the env vars!')

    fname = sys.argv[1]

    # To generate a new token:
    # From Azure portal, choose the course's Databricks workspace (or create it if this is the first time).
    # Launch the Workspace
    # you will arrive to a url similar to https://adb-7838547822330032.12.azuredatabricks.net/?o=7838547822330032#
    #
    # choose your username - User Settings - Access tokens - generate new token
    #
    # Using/Creating a policy:
    #  https://learn.microsoft.com/en-us/azure/databricks/administration-guide/clusters/policies
    # (Cluster policies require the Premium plan)
    # Using the UI: open the DBR portal - compute (in the left pane), Policies tab. Choose "Shared Compute". Copy the policy ID

    client = DataBricksClusterOps(host='https://' + host, token=token)
    #client.print_clusters()

    # If you need to purge all clusters in this workspace: (need to type 'yes')
    # client.permanent_delete_all_clusters(verbose=True)

    nGroups = create_users_from_moodle(client, fname, verbose=True)
    create_clusters(nGroups,verbose=True)

    allgroups = [ f"g{n+1}" for n in range(nGroups)]
    client.attach_groups_to_clusters(allgroups, verbose=True)


    print("Once the groups and users are created, you can go to the DataBricks portal to add permission to use the workspace.\n "
          "choose your name - Admin Console. Choose 'all_student_groups'. Choose 'Entitlements'. Select 'Workspace access' checkbox")

