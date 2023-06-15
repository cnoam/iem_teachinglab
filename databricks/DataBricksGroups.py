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
        return self.groups_api.list_members(groupname)['members']


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    host = 'https://' + os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')
    print(DataBricksGroups(host=host, token=token).get_group_members('g10'))