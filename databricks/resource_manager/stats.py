import logging
import re
import concurrent.futures
import time
from DataBricksClusterOps import DataBricksClusterOps, DataBricksGroups


def print_user_allocation_clusters(groups_api: DataBricksGroups, cluster_api: DataBricksClusterOps, logger: logging.Logger):
    """ print a table  sorted by cluster name:
    [
    [ cluster name, group name, [user_emails,...] ]
     ...
    ]
    """

    # As long as the API request is done using sync client, I can not use asyncio.
    # fallback to threadpool

    def get_data_from_cluster(cluster: dict):
        permissions = cluster_api.get_cluster_permission(cluster['cluster_id'])
        perms = []
        for g in permissions['access_control_list']:
            try:
                perms.append({'group_name': g['group_name'], 'permission': g['all_permissions'][0]['permission_level']})
            except KeyError as ex:
                logger.warning(f"Skipping permissions of user without a group in cluster {c['cluster_name']}")

        matcher = re.compile("^g[\d]{1,2}")
        user_groups = list(filter(lambda x: matcher.match(x['group_name']), perms))
        if user_groups:
            user_names = groups_api.get_group_members(user_groups[0]['group_name'])
        else:
            user_names = []
        return {'cluster_id': cluster['cluster_id'], 'cluster_name': cluster['cluster_name'],'groups': user_groups, 'users': user_names}

    clusters = cluster_api.get_clusters()
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(100, len(clusters))) as executor:
        futures = [executor.submit(get_data_from_cluster, value) for value in clusters]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    delta = time.time() - start
    logger.info(f"collecting info from {len(clusters)} clusters took {delta:.2} Seconds")

    # now that we have all the info, print it as we want
    f = []
    for v in results:
        try:
            cluster_name = v['cluster_name']
            gname = v['groups'][0]['group_name']
            permission = v['groups'][0]['permission']
            users = [u['user_name'] for u in v['users']]
            clipped = [x[: x.find('@')] for x in users]
        except (KeyError, IndexError):
            gname = permission = ''
            clipped = []
        finally:
            f.append([cluster_name, gname, permission, clipped]
                     )
    f.sort(key=lambda x: int(x[0][8:]))  # drop the "cluster_" prefix
    for line in f:
        print(f"{line[0]},\t{line[1]:4}, {line[2]},\t {' : '.join(line[3])}")


def print_user_allocation_clusters_sync(groups_api: DataBricksGroups,
                                        cluster_api: DataBricksClusterOps, logger: logging.Logger):
    "sync version . Each API call is about 4.5 seconds. 4.5 * len(clusters) == a long time"
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
