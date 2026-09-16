"""
Enforcement lever for the serverless quota backend: SCIM add/remove of a
student group_NN in/out of `all_student_groups` (plan 2.5).

Confirmed live (2026-09-16, workspace 94290_2026): removing a group blocks
new command dispatch and page access, reliably -- but does NOT terminate a
command already running. See plan 2.5 for the full evidence and caveats
(pure-Python confirmed; Spark untested, assumed the same). Restoring is
idempotent (adding an already-present member is a no-op).

Uses the `databricks-sdk` package (databricks.sdk.WorkspaceClient) --
migrated 2026-09-16 from `requests`, which was a necessity at the time (see
group_map.py's docstring / serverless_quota_plan.md for the now-resolved
package-naming collision), not a preference.
"""
import logging

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError
from databricks.sdk.service.iam import Patch, PatchOp, PatchSchema

ALL_STUDENT_GROUPS_NAME = "all_student_groups"


def find_group_id(client: WorkspaceClient, display_name: str):
    """Returns the SCIM group id for a workspace group by display name, or
    None if no such group exists."""
    group = next(client.groups.list(filter=f'displayName eq "{display_name}"'), None)
    return group.id if group else None


def block_group(client: WorkspaceClient, group_name: str, logger: logging.Logger = None) -> bool:
    """
    Removes group_name from all_student_groups (SCIM PATCH remove). Returns
    True on success; False if either group id couldn't be resolved, or if
    the PATCH itself raised (`DatabricksError`, e.g. a permission problem or
    transient API failure) -- both are logged, not raised, so a failure on
    one group doesn't abort the whole poll cycle for the others (matching
    the plan's per-group loop in ServerlessBackend, which has no try/except
    of its own around this call).
    """
    logger = logger or logging.getLogger('SERVERLESS_ENFORCE')
    parent_id = find_group_id(client, ALL_STUDENT_GROUPS_NAME)
    member_id = find_group_id(client, group_name)
    if not parent_id or not member_id:
        logger.error(
            f"Cannot block {group_name}: group id lookup failed "
            f"(parent={parent_id}, member={member_id})"
        )
        return False
    try:
        client.groups.patch(
            parent_id,
            operations=[Patch(op=PatchOp.REMOVE, path=f'members[value eq "{member_id}"]')],
            schemas=[PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
        )
    except DatabricksError as ex:
        logger.error(f"Cannot block {group_name}: SCIM patch failed: {ex}")
        return False
    logger.info(f"Blocked {group_name}: removed from {ALL_STUDENT_GROUPS_NAME}")
    return True


def restore_group(client: WorkspaceClient, group_name: str, logger: logging.Logger = None) -> bool:
    """
    Adds group_name back to all_student_groups (SCIM PATCH add). Idempotent
    -- safe to call unconditionally for every group_NN, whether or not it
    was actually blocked, matching the classic backend's
    restore_cluster_permissions() style (unconditional restore of all
    groups, simple and robust). Returns True on success; False if either
    group id couldn't be resolved, or if the PATCH itself raised
    (`DatabricksError`) -- both logged, not raised, so one group's restore
    failure doesn't stop the others from being restored.
    """
    logger = logger or logging.getLogger('SERVERLESS_ENFORCE')
    parent_id = find_group_id(client, ALL_STUDENT_GROUPS_NAME)
    member_id = find_group_id(client, group_name)
    if not parent_id or not member_id:
        logger.error(
            f"Cannot restore {group_name}: group id lookup failed "
            f"(parent={parent_id}, member={member_id})"
        )
        return False
    try:
        client.groups.patch(
            parent_id,
            operations=[Patch(op=PatchOp.ADD, path='members', value=[{'value': member_id}])],
            schemas=[PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
        )
    except DatabricksError as ex:
        logger.error(f"Cannot restore {group_name}: SCIM patch failed: {ex}")
        return False
    logger.info(f"Restored {group_name}: added back to {ALL_STUDENT_GROUPS_NAME}")
    return True
