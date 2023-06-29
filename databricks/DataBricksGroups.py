from databricks_cli.sdk.api_client import ApiClient
from databricks_cli.groups.api import GroupsApi



class DataBricksGroups:
    """
    Use Databricks API to administer groups.

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


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    host = 'https://' + os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')
    dbr = DataBricksGroups(host=host, token=token)
    for i in range(52):
        name = 'g'+str(i+1)
        members = dbr.get_group_members(name)
        try:
            first = members[0]
            second = members[1]
            print(f"{i}, {first['user_name']}, {second['user_name']}")
        except IndexError:
            print(f"{i}: no pair.")
