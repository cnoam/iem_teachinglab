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

    def __init__(self,host:str, token:str):
        self.api_client = ApiClient(host=host,token=token)
        self.token = token
        self.host = host


    def get_clusters(self):
        """ get the list of currently defined clusters (both online and offline)
        :return list( dict( cluster parameters))
        """
        clusters_api = ClusterApi(self.api_client)
        clusters_list = clusters_api.list_clusters()
        return clusters_list['clusters']

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

    def create_cluster(self, name: str):
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
                  "min_workers": 2,
                  "max_workers": 6
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
              "autotermination_minutes": 15,
              "enable_elastic_disk": true,
              "cluster_source": "UI",
              "init_scripts": [],
              "policy_id": "6063781CC90049CA",
              "data_security_mode": "NONE",
              "runtime_engine": "STANDARD"
        }""")
        tmp = template.substitute(cluster_name=name)
        json_spec = json.loads(tmp)
        return self.create_cluster_from_spec(json_spec)

    def delete_cluster(self, name):
        """Terminate a cluster, but do not delete it.
        The name is misleading because this is how the API works
        :return: None
        :raise KeyError if name not found or not unique
        """

        clusters = self.get_clusters()
        r = list(filter(lambda c: c['cluster_name'] == name, clusters))
        if len(r) == 0:
            raise KeyError(f'{name} not found in the list of clusters')
        if len(r) > 1:
            raise KeyError(f'There are multiple clusters with name:{name}. Refuse to delete')
        r = r[0]
        ClusterApi(self.api_client).delete_cluster(cluster_id=r['cluster_id'])

    ##
    ##
    ##
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


def create_users_from_moodle(dbapi: DataBricksClusterOps, filename:str) -> int :
    """
    Read Moodle user groups, and create Databricks groups with these users
    The groups and users MUST NOT exist before in Databricks workspace.

    :param dbapi: initialized connection to Databricks API
    :param filename: CSV file in Moodle format, group assignment
    :return: number of users created in the workspace
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
    return nCreated


def test_user_creation_from_moodle(client):
    create_users_from_moodle(client, '/home/cnoam/Desktop/94290w2022.csv')


def create_clusters(how_many:int):
    for i in range(how_many):
        resp1 = client.create_cluster( f"cluster_{i}") # create the cluster and turn it ON
        if resp1:
            client.delete_cluster(f"cluster_{i}")  # turn the cluster OFF. We don't want to run it now.
        else:
            print(f"Failed created cluster {i}")

if __name__ == "__main__":
    # host = os.getenv('DATABRICKS_HOST')
    # token = os.getenv('DATABRICKS_TOKEN')
    # if host is None or token is None:
    #     raise RuntimeError('must set the env vars!')
    # These will be in an env var

    # To generate a new token:
    # choose your user name - User Settings - Access tokens - generate new token
    DATABRICKS_TOKEN = "your token"
    DATABRICKS_HOST = "adb-4286500221395801.1.azuredatabricks.net" # without 'https://'
    client = DataBricksClusterOps(host='https://' + DATABRICKS_HOST, token=DATABRICKS_TOKEN)
    # client.print_clusters()
    create_clusters(32)

    #client.delete_cluster("cluster_2")
    #resp = client.create_group("unittesting")
    #print("create group:", resp.status_code)

    # n = client.create_users(['test_user1', 'test_user2', 'test_user3'])
    # assert n == 3

    #test_user_creation_from_moodle(client)

    print("Once the groups and users are created, you can go to the DataBricks portal to add permission to use the workspace.\n "
          "choose your name - Admin Console. Choose 'all_student_groups'. Choose 'Entitelements'. Select 'Workspace access' checkbox")

