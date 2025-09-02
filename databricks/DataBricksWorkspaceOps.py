# Purpose: delete all user folders except for a list of users

from databricks.sdk import WorkspaceClient


def list_users_dirs(token, host):
    """ This works fine with a token generated in the workspace GUI"""

    w = WorkspaceClient(token=token, host=host)
    names = []
    for i in w.workspace.list(f'/Users/', recursive=False):
        if i.object_type.name == 'DIRECTORY':
            names.append(i.path)
    assert len(names) > 0
    return names


def delete_user_folders(token, host, exclusion_list):
    """ Delete the workspace folders of all users except for the ones in the exclusion list.
    NOTE: if you get an error such as:
    "databricks.sdk.core.DatabricksError: Folder dds.cloud@technion.ac.il is protected"
    it means that the user still exists. You need to first delete the user (from UI or script) and then run this script.
    """
    w = WorkspaceClient(token=token, host=host)
    exclusion_list = ['/Users/' +i for i in exclusion_list]
    user_folders = list_users_dirs(token, host)
    for folder in user_folders:
        if folder not in exclusion_list:
            print(f'deleting {folder}')
            w.workspace.delete(folder, recursive=True)


import os
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_WS_TOKEN')
    if host is None or token is None:
        raise RuntimeError('must set the env vars!')

    delete_folders = False
    if delete_folders:
        delete_user_folders(token, host, ['cnoam@technion.ac.il','efrat.maimon@technion.ac.il',
                                      'test@technion.ac.il'])
