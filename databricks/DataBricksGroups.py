import requests
from databricks_cli.sdk.api_client import ApiClient
from databricks_cli.groups.api import GroupsApi


class DataBricksGroups:
    """
    Use Databricks API to administer groups.
    This is a thin wrapper around class GroupsApi

    https://docs.databricks.com/dev-tools/python-api.html

    This class uses API 2.0 (legacy)
    """

    def __init__(self,host:str, token:str):
        self.api_client = ApiClient(host=host,token=token)
        self.token = token
        self.host = host
        self.groups_api = GroupsApi(self.api_client)

    def get_group_members(self, groupname:str) -> list:
        try:
            return self.groups_api.list_members(groupname)['members']
        except KeyError:
            return []

    def list_groups(self):
        return self.groups_api.list_all()

    def list_users(self):
        """Get a dictionary of all users in the workspace
        See the docs how to filter the returned list by attributes or filtering. """
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url=f"{self.host}/api/2.0/preview/scim/v2/Users?&count=10000", headers=headers)
        response.raise_for_status()
        return response.json()

    def create_group(self, group_name:str):
        import json
        import requests

        headers = {"Authorization": f"Bearer {self.token}"}
        url = f'{self.host}/api/2.0/preview/scim/v2/Groups'
        j = json.dumps({"displayName": group_name})
        resp = requests.post(url, headers=headers, data=j)
        # return self.groups_api.create(group_name) #  as of 2024-06-25, this api is broken
        return resp

    def delete_group(self, group_name:str)->int :
        """delete a group.
        :return: HTTP status code 200, 403, 404"""
        try:
            self.groups_api.delete(group_name)
        except requests.exceptions.HTTPError as ex:
            return ex.response.status_code
        return 200

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

    def get_user_details(self, id_):
        """given user ID (as a string containing integer), return the user details"""
        # https://docs.databricks.com/api/latest/scim/index.html#operation/getUser
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url=f"{self.host}/api/2.0/preview/scim/v2/Users/{id_}", headers=headers)
        response.raise_for_status()
        return response.json()

    def add_or_delete_users(self, users: list[int], delete_user: bool):
        """ Add/delete users to the DBR workspace.
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
                data = """{{"schemas":["urn:ietf:params:scim:schemas:core:2.0:User"],"userName":"{user}"}}""".format(
                    user=user)
                response = requests.api.post(url=url, headers=headers, data=data)
            if response:  # this format of checking will cover also 201, 304 etc.
                num_ok += 1
        return num_ok

if __name__ == "__main__":
    import os
    import re
    from dotenv import load_dotenv
    load_dotenv()

    host =  os.getenv('DATABRICKS_HOST')
    assert host is not None
    host = 'https://' + host
    token = os.getenv('DATABRICKS_TOKEN')
    assert token is not None
    groups_api = DataBricksGroups(host=host, token=token)

    names = groups_api.list_groups()['group_names']
    names = [n for n in names if re.match(r'g\d{1,2}',n)]

    for name in names:
        members = groups_api.get_group_members(name)
        print(f"{name}: " , end='')
        for name in members:
            a = name['user_name']
            a = a[0:a.find('@')]
            print(f"{a}  ", end='')
        print("")
