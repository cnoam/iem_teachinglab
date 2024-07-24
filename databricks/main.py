# command line tool to manage Databricks workspace clusters, users and groups
#   for a course. The list of users is given in a CSV file generated in Moodle system.
# Noam Cohen 2024-07-02 10:50

import json
import logging
import sys, re, pprint

from DataBricksClusterOps import DataBricksClusterOps, DataBricksGroups

dry_run = False

logger = logging.getLogger('DBR_cluster_ops')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
logger.addHandler(ch)


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
             # if the code is 409, the schema is '{"schemas":["urn:ietf:params:scim:api:messages:2.0:Error"],"detail":"Group with name all_student_groups already exists.","status":"409"}'
             # if it is 403, it is { ... , 'error_code': integer}
             if res.status_code == 409:
                return
             response.raise_for_status()

    groups = MoodleFileParser.parse_moodle_csv(filename)

    groups_api = DataBricksGroups(host=dbapi.host, token=dbapi.token)

    # create a master group that contains all the groups. This will make it
    # easy for the admin to give access.
    master_group_name = "all_student_groups"
    response = groups_api.create_group(master_group_name)
    raise_for_status_unless_exists(response)

    for group, users in groups.items():
        # the 'users' is full email address, all in the same domain.
        # let's remove the domain -- we know that the name will be unique in a single domain.
        # shortnames = [u[: u.rfind('@')]  for u in users]
        group_name = "g" + str(group)
        response = groups_api.create_group(group_name)
        raise_for_status_unless_exists(response)

        # Add the newly created group to the "master group"
        response = groups_api.add_member_to_group(group_name, master_group_name, is_user=False)
        raise_for_status_unless_exists(response)

        nCreated = groups_api.create_users(users)
        if nCreated != len(users):
            print(f"Warning: at least one of {users} was not created")
        for u in users:
            response = groups_api.add_member_to_group(u, group_name, is_user=True)
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

    for j in range(how_many):
        i = j +1
        try:
            resp1 = cluster_api.create_cluster(f"cluster_{i}", policy_id=policy_id)  # create the cluster and turn it ON
            if resp1:
                cluster_api.delete_cluster(f"cluster_{i}")  # turn the cluster OFF. We don't want to run it now.
            else:
                print(f"Failed created cluster {i}")
            if verbose:
                print(f"cluster {i}", end=' ')
        except AttributeError as e:
            print(f"{e}  ==> skipped")

    if verbose:
        print('\n')


def delete_all_users(groups_api: DataBricksGroups, exception_list: list[str]):
    ok = input("About to permanently delete ALL USERS. If this is ok, type 'yes': ")
    if ok != 'yes':
        print("Cancelled.")
        return
    users = groups_api.list_users()
    users_to_delete = filter(lambda u: u['emails'][0]['value'] not in exception_list, users['Resources'])
    id_to_delete = [u['id'] for u in users_to_delete]
    num_deleted = groups_api.delete_users(id_to_delete)
    print(f"deleted {num_deleted} users")


def delete_all_groups(groups_api: DataBricksGroups):
    ok = input("About to permanently delete ALL GROUPS. If this is ok, type 'yes': ")
    if ok != 'yes':
        print("Cancelled.")
        return
    group_names = groups_api.list_groups()
    p=re.compile("^g[\d]{1,2}")

    names_to_delete = [s for s in group_names if p.match(s)]

    num_deleted = 0
    for g in names_to_delete:
        resp_code= groups_api.delete_group(g)
        num_deleted += resp_code == 200 # https status

    print(f"deleted {num_deleted} groups")



def create_clusters_and_users(moodle_filename: str):
    nGroups = create_users_from_moodle(cluster_api, moodle_filename, verbose=True)
    create_clusters(nGroups, verbose=True)

    allgroups = [f"g{n + 1}" for n in range(nGroups)]
    cluster_api.attach_groups_to_clusters(allgroups, verbose=True)

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


def pin_clusters(client: DataBricksClusterOps):
    """PIN all the clusters in the workspace."""
    clusters = client.get_clusters()
    for c in clusters:
        client.pin_cluster(c)


def print_usage():
    print("""
    Add/delete clusters/groups/users in a Databricks cluster.
    
    Try prog --help
    
    
    To generate a new token:
    From Azure portal, choose the course's Databricks workspace (or create it if this is the first time).
    Launch the Workspace
    you will arrive to a url similar to https://adb-7838547822330032.12.azuredatabricks.net/?o=7838547822330032#

    choose your username - User Settings - Developer - Access tokens - generate new token

    Using/Creating a policy:
     https://learn.microsoft.com/en-us/azure/databricks/administration-guide/clusters/policies
    (Cluster policies require the Premium plan)
    Using the UI: open the DBR portal - compute (in the left pane), Policies tab. Choose "Shared Compute". Copy the policy ID
    """)


def print_groups():
    groups_api = DataBricksGroups('https://' + host, token)
    names = groups_api.list_groups()
    names = [n for n in names if re.match(r'g\d{1,2}',n)]
    names.sort(key= lambda x : int(x[1:]))
    pprint.pprint(names)


def print_users(groups_api: DataBricksGroups):
    values = groups_api.list_users()
    emails =[ x['emails'][0]['value'] for x in values['Resources'] ]
    pprint.pprint(emails)


def print_user_allocation_clusters(groups_api: DataBricksGroups, cluster_api: DataBricksClusterOps):
    """ print a table  sorted by cluster name:
    [
    [ cluster name, group name, [user_emails,...]]
    ...
    ]"""

    res = {}
    clusters = cluster_api.get_clusters()
    for c in clusters:
        permissions = cluster_api.get_cluster_permission(c['cluster_id'])
        # {
        # "object_id":"/clusters/0626-112719-jy3n8ws2",
        # "object_type":"cluster",
        # "access_control_list":
        #   [  {"group_name":"admins",
        #       "all_permissions":[
        #           {"permission_level":"CAN_MANAGE",
        #            "inherited":true,
        #            "inherited_from_object":["/clusters/"]}]
        #        },
        #       {"group_name":"g13","all_permissions":[{"permission_level":"CAN_RESTART","inherited":false}]}]}'

        # for each cluster, get some info
        perms = []
        for g in permissions['access_control_list']:
            try:
                perms.append({'group_name': g['group_name'], 'permission': g['all_permissions'][0]['permission_level']} )
            except KeyError as ex:
                logger.warning(f"Skipping permissions of user without a group in cluster {c['cluster_name']}")

        matcher = re.compile("^g[\d]{1,2}")
        user_groups = list(filter(lambda x: matcher.match(x['group_name']), perms))
        if user_groups:
            user_names = groups_api.get_group_members(user_groups[0]['group_name'])
        else:
            user_names = []
        res[c['cluster_name']] = { 'groups':user_groups, 'users': user_names}

    # now that we have all the info, print it as we want
    f = []
    for k, v in res.items():
        try:
            gname = v['groups'][0]['group_name']
            permission = v['groups'][0]['permission']
            users = [u['user_name'] for u in v['users']]
            clipped = [x[: x.find('@')] for x in users]
        except (KeyError, IndexError):
            gname = permission = ''
            clipped = []
        finally:
            f.append([k, gname, permission, clipped]
                     )
    f.sort(key=lambda x: int(x[0][8:]))  # drop the "cluster_" prefix
    for line in f:
        print(f"{line[0]},\t{line[1]},\t, {line[2]},\t {' : '.join(line[3])}")



def print_user_in_groups(groups_api: DataBricksGroups):

    names = groups_api.list_groups()
    names = [n for n in names if re.match(r'g\d{1,2}', n)]

    for name in names:
        members = groups_api.get_group_members(name)
        print(f"{name}: ", end='')
        for name in members:
            a = name['user_name']
            a = a[0:a.find('@')]
            print(f"{a}  ", end='')
        print("")


if __name__ == "__main__":

    if len(sys.argv) == 1:
        print_usage()
        exit(0)
    from dotenv import load_dotenv
    import os, argparse
    load_dotenv()

    host = os.getenv('DATABRICKS_HOST')
    token = os.getenv('DATABRICKS_TOKEN')
    policy_id = os.getenv('POLICY_ID','')
    if host is None or token is None:
        raise RuntimeError('must set the env vars!')

    groups_api = DataBricksGroups(host='https://' + host, token=token)
    cluster_api = DataBricksClusterOps(host_='https://' + host, token_=token)

    parser = argparse.ArgumentParser(description="Process a CSV file (optional)")
    parser.add_argument("--create_from_csv", type=str, help="Path to the CSV file")
    parser.add_argument("--print_clusters", action="store_true", default=False, help="Print the cluster names")
    parser.add_argument("--print_groups", action="store_true", default=False, help="Print the group names")
    parser.add_argument("--print_users", action="store_true", default=False, help="Print the users names")
    parser.add_argument("--print_user_groups", action="store_true", default=False, help="Print the users in each group")
    parser.add_argument("--print_user_groups_clusters", action="store_true", default=False, help="Print a nice table:for each cluster which group is connected and who are the users")
    parser.add_argument("--delete_all_users", action="store_true", default=False, help="Delete all workspace users except the VIP (need to type 'yes')")
    parser.add_argument("--delete_all_groups", action="store_true", default=False, help="Delete all workspace groups (need to type 'yes')")
    parser.add_argument("--purge_clusters", action="store_true", default=False,   help="Delete all clusters (need to type 'yes') ")
    parser.add_argument("--test_email", action="store_true", default=False,   help="Send a test email message")
    #parser.add_argument("--install_NLP_libs", action="store_true", default=False, help="install  some needed libs")
    args = parser.parse_args()

    #install_libs_for_NLP(client)
    if args.create_from_csv:
        # Given a Moodle file, create users and groups in Databricks workspace
        create_clusters_and_users(args.create_from_csv)
        update_auto_termination(cluster_api, 22) # 22 minutes
        pin_clusters(cluster_api)

    if args.print_clusters:
        cluster_api.print_clusters()

    if args.print_groups:
        print_groups()

    if args.print_users:
        print_users(groups_api)

    if args.print_user_groups:
        print_user_in_groups(groups_api)

    if args.print_user_groups_clusters:
        print_user_allocation_clusters(groups_api=groups_api, cluster_api=cluster_api)

    if args.delete_all_users:
        # delete all users in this workspace except for a few:
        # (it will not delete the groups)
        g = DataBricksGroups(host,token)
        delete_all_users(groups_api=g, exception_list =['cnoam@technion.ac.il'])
        print("To delete the workspace folders of the deleted users, use DatabricksClusterOps.py script")

    if args.delete_all_groups:
        # delete all groups in this workspace
        # (it will not delete the users)
        g = DataBricksGroups(host = "https://"+host,token=token)
        delete_all_groups(groups_api=g)
        print("To delete the workspace folders of the deleted users, use DatabricksClusterOps.py script")

    if args.purge_clusters:
        # purge all clusters in this workspace: (need to type 'yes')
        cluster_api.permanent_delete_all_clusters(verbose=True)

    if args.test_email:
        from resource_manager.user_mail import send_emails
        send_emails("test message","body of message", ['dds.lab@technion.ac.il'], logger)




