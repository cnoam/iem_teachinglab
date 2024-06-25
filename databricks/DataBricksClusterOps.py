import json
from enum import Enum
import logging
import requests
from databricks_cli.clusters.api import ClusterApi
from databricks_cli.dbfs.api import DbfsApi
from databricks_cli.dbfs.dbfs_path import DbfsPath
from databricks_cli.sdk.api_client import ApiClient

dry_run = False

logger = logging.getLogger('DBR_cluster_ops')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
logger.addHandler(ch)


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
        response = requests.api.patch(url=url, headers=headers, data=json.dumps(config))
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
            self.set_cluster_permission(self.cluster_from_name(cluster_name)['cluster_id'], gname, self.ClusterPermission.RESTART)

    def create_group(self, group_name: str):
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

    def create_users(self, users: list) -> int:
        """
        Add users to Databricks workspace.
        If a user is already added, the cluster will return 409 and will not add the user again.

        :param users: list(string of user's email)
        :return: number of successfully added users
        """
        return self.add_or_delete_users(users, delete_user=False)

    def delete_users(self, users: list):
        """
        Delete users from Databricks workspace.
        If a user is already deleted, the cluster will return 404 and will not delete the user again.

        :param users: list(string of user's email)
        :return: number of successfully deleted users
        """
        return self.add_or_delete_users(users, delete_user=True)

    def list_users(self):
        """Get a dictionary of all users in the workspace
        See the docs how to filter the returned list by attributes or filtering. """
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url=f"{self.host}/api/2.0/preview/scim/v2/Users?&count=10000", headers=headers)
        response.raise_for_status()
        return response.json()

    def get_user_details(self, id_):
        """given user ID (as a string containing integer), return the user details"""
        # https://docs.databricks.com/api/latest/scim/index.html#operation/getUser
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url=f"{self.host}/api/2.0/preview/scim/v2/Users/{id_}", headers=headers)
        response.raise_for_status()
        return response.json()

    def add_or_delete_users(self, users: list[int], delete_user: bool):
        """ Add/delete users to the workspace.
            If an error happens during the operation-> partial change.
            see https://docs.databricks.com/api/azure/workspace/users/delete
        """
        headers = {"Authorization": f"Bearer {self.token}"}

        num_ok = 0
        for user in users:
            if delete_user:
                id = user
                url = f"{self.host}/api/2.0/preview/scim/v2/Users/{id}"
                response = requests.api.delete(url, headers=headers)
                response.raise_for_status()
            else:
                url = f'{self.host}/api/2.0/preview/scim/v2/Users'
                data = """{{"schemas":["urn:ietf:params:scim:schemas:core:2.0:User"],"userName":"{user}"}}""".format(user=user)
                response = requests.api.post(url=url, headers=headers, data=data)
            if response:  # this format of checking will cover also 201, 304 etc.
                num_ok += 1
        return num_ok

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

def create_users_from_moodle(dbapi: DataBricksClusterOps, filename: str, verbose: bool) -> int:
    """
    Read Moodle user groups, and create Databricks groups with these users
    The groups and users MUST NOT exist before in Databricks workspace.

    :param dbapi: initialized connection to Databricks API
    :param filename: CSV file in Moodle format, group assignment
    :return: number of groups created in the workspace
    :raise HTTPstatus if any of the requests failed
    """
    from MoodleFileParser import MoodleFileParser

    if dry_run:
        return 0

    def raise_for_status_unless_exists(res):
         if 400 <= res.status_code < 500:
             text = json.loads(res.text)
             if text['error_code'] == "RESOURCE_ALREADY_EXISTS":
                return
             response.raise_for_status()

    groups = MoodleFileParser.parse_moodle_csv(filename)

    # create a master group that contains all the groups. This will make it
    # easy for the admin to give access.
    master_group_name = "all_student_groups"
    response = dbapi.create_group(master_group_name)
    raise_for_status_unless_exists(response)

    for group, users in groups.items():
        # the 'users' is full email address, all in the same domain.
        # let's remove the domain -- we know that the name will be unique in a single domain.
        # shortnames = [u[: u.rfind('@')]  for u in users]
        group_name = "g" + str(group)
        response = dbapi.create_group(group_name)
        raise_for_status_unless_exists(response)

        # Add the newly created group to the "master group"
        response = dbapi.add_member_to_group(group_name, master_group_name, is_user=False)
        raise_for_status_unless_exists(response)

        nCreated = dbapi.create_users(users)
        if nCreated != len(users):
            print(f"Warning: at least one of {users} was not created")
        for u in users:
            response = dbapi.add_member_to_group(u, group_name, is_user=True)
            response.raise_for_status()

        if verbose:
            print(f"{group}", end=' ')
    if verbose:
        print('\n')
    return len(groups)


def test_user_creation_from_moodle(client):
    create_users_from_moodle(client, '/home/cnoam/Desktop/94290w2022.csv')


def create_clusters(how_many: int, verbose: bool = False):
    global dry_run
    if dry_run:
        print(f"FAKE: create {how_many} clusters")
        return

    for i in range(how_many):
        try:
            resp1 = client.create_cluster(f"cluster_{i}", policy_id=policy_id)  # create the cluster and turn it ON
            if resp1:
                client.delete_cluster(f"cluster_{i}")  # turn the cluster OFF. We don't want to run it now.
            else:
                print(f"Failed created cluster {i}")
            if verbose:
                print(f"cluster {i}", end=' ')
        except AttributeError as e:
            print(f"{e}  ==> skipped")

    if verbose:
        print('\n')


def delete_all_users(exception_list: list[str]):
    users = client.list_users()
    users_to_delete = filter(lambda u: u['emails'][0]['value'] not in exception_list, users['Resources'])
    id_to_delete = [u['id'] for u in users_to_delete]
    num_deleted = client.delete_users(id_to_delete)
    print(f"deleted {num_deleted} users")


def create_clusters_and_users(moodle_filename: str):
    nGroups = create_users_from_moodle(client, moodle_filename, verbose=True)
    create_clusters(nGroups, verbose=True)

    allgroups = [f"g{n + 1}" for n in range(nGroups)]
    client.attach_groups_to_clusters(allgroups, verbose=True)

    print("Once the groups and users are created, you can go to the DataBricks portal to add permission to use the workspace.\n "
          "choose your name - Admin Console. 'Identity and access' | 'Groups' .\n"
          "Choose 'all_student_groups'. Choose 'Entitlements'. Select 'Workspace access' checkbox")


def install_libs_for_NLP(c :DataBricksClusterOps):
    """Install the libraries needed for the NLP task to all the clusters"""
    clusters = c.get_clusters()
    #clusters_ids = [c['cluster_id'] for c in clusters]
    for cluster in clusters:
        cid = cluster['cluster_id']
        result = c.install_libraries(cid, [
            {"pypi": {"package": "spark-nlp", "repo": "https://pypi.org/simple"}},
            {"pypi": {"package": "nltk", "repo": "https://pypi.org/simple"}},
            {"pypi": {"package": "spacy", "repo": "https://pypi.org/simple"}},
            {"pypi": {"package": "gensim", "repo": "https://pypi.org/simple"}},
            {"maven": {"coordinates": "com.johnsnowlabs.nlp:spark-nlp_2.12:5.1.2"}}  # add your own maven library here
        ])
        if result:
            logger.info("Installed libraries to cluster " + cid  + "("+ cluster['cluster_name'] + ")")
        else:
            logger.error("Failed to install libraries to cluster " + cid)

def update_auto_termination(c: DataBricksClusterOps, minutes: int):
    """Set the auto-termination time of all the clusters to the given number of minutes"""
    clusters = c.get_clusters()
    for cluster in clusters:
        cid = cluster['cluster_id']
        result = c.update_auto_termination(cluster, minutes)
        if result:
            logger.info("Updated auto-termination time of cluster " + cid + " to " + str(minutes) + " minutes")
        else:
            logger.error("Failed to update auto-termination time of cluster " + cid + " to " + str(minutes) + " minutes")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    import sys, os

    # x = sys.argv
    # if len(sys.argv) != 2:
    #     print("Usage: prog groups_in_moodle.csv")
    #     exit(1)

    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')
    policy_id = os.getenv('POLICY_ID')
    if host is None or token is None:
        raise RuntimeError('must set the env vars!')

    #fname = sys.argv[1]

    # To generate a new token:
    # From Azure portal, choose the course's Databricks workspace (or create it if this is the first time).
    # Launch the Workspace
    # you will arrive to a url similar to https://adb-7838547822330032.12.azuredatabricks.net/?o=7838547822330032#
    #
    # choose your username - User Settings - Developer - Access tokens - generate new token
    #
    # Using/Creating a policy:
    #  https://learn.microsoft.com/en-us/azure/databricks/administration-guide/clusters/policies
    # (Cluster policies require the Premium plan)
    # Using the UI: open the DBR portal - compute (in the left pane), Policies tab. Choose "Shared Compute". Copy the policy ID

    client = DataBricksClusterOps(host_='https://' + host, token_=token)
    #install_libs_for_NLP(client)
    update_auto_termination(client, 22)

    client.print_clusters()

    # delete all users in this workspace except for a few:
    # (it will not delete the groups)
    # delete_all_users(exception_list =['cnoam@technion.ac.il', 'ilanit.sobol@campus.technion.ac.il'])
    # print("To delete the workspace folders of the deleted users, use DatabricksClusterOps.py script")
    # purge all clusters in this workspace: (need to type 'yes')
    #client.permanent_delete_all_clusters(verbose=True)

    # Given a Moodle file, create users and groups in Databricks workspace
    # create_clusters_and_users(fname)

