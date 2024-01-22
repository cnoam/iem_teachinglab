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

    def list_all(self):
        return self.groups_api.list_all()


if __name__ == "__main__":
    import os
    import re
    from dotenv import load_dotenv
    load_dotenv()

    host = 'https://' + os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')
    dbr = DataBricksGroups(host=host, token=token)
    names = dbr.list_all()['group_names']
    names = [n for n in names if re.match(r'g\d{1,2}',n)]

    for name in names:
        members = dbr.get_group_members(name)
        print(f"{name}: " , end='')
        for name in members:
            a = name['user_name']
            a = a[0:a.find('@')]
            print(f"{a}  ", end='')
        print("\n")
