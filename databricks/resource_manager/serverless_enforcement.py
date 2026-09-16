"""
Enforcement lever for the serverless quota backend: SCIM add/remove of a
student group_NN in/out of `all_student_groups` (plan 2.5).

Confirmed live (2026-09-16, workspace 94290_2026): removing a group blocks
new command dispatch and page access, reliably -- but does NOT terminate a
command already running. See plan 2.5 for the full evidence and caveats
(pure-Python confirmed; Spark untested, assumed the same). Restoring is
idempotent (adding an already-present member is a no-op).

Uses raw `requests` against SCIM -- see group_map.py's docstring for why
the databricks-sdk package is unimportable from inside this codebase.
"""
import logging

import requests

from .dbr_host import normalize_dbr_host

ALL_STUDENT_GROUPS_NAME = "all_student_groups"


def _scim_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def find_group_id(host: str, token: str, display_name: str):
    """Returns the SCIM group id for a workspace group by display name, or
    None if no such group exists."""
    host = normalize_dbr_host(host)
    resp = requests.get(
        f"{host}/api/2.0/preview/scim/v2/Groups",
        headers=_scim_headers(token),
        params={"filter": f'displayName eq "{display_name}"'},
        timeout=30,
    )
    resp.raise_for_status()
    resources = resp.json().get('Resources', [])
    return resources[0]['id'] if resources else None


def block_group(host: str, token: str, group_name: str, logger: logging.Logger = None) -> bool:
    """
    Removes group_name from all_student_groups (SCIM PATCH remove). Returns
    True on success, False if either group id couldn't be resolved (logged,
    not raised -- a lookup failure shouldn't crash the whole poll cycle for
    other groups).
    """
    logger = logger or logging.getLogger('SERVERLESS_ENFORCE')
    host = normalize_dbr_host(host)
    parent_id = find_group_id(host, token, ALL_STUDENT_GROUPS_NAME)
    member_id = find_group_id(host, token, group_name)
    if not parent_id or not member_id:
        logger.error(
            f"Cannot block {group_name}: group id lookup failed "
            f"(parent={parent_id}, member={member_id})"
        )
        return False
    resp = requests.patch(
        f"{host}/api/2.0/preview/scim/v2/Groups/{parent_id}",
        headers=_scim_headers(token),
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "remove", "path": f'members[value eq "{member_id}"]'}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    logger.info(f"Blocked {group_name}: removed from {ALL_STUDENT_GROUPS_NAME}")
    return True


def restore_group(host: str, token: str, group_name: str, logger: logging.Logger = None) -> bool:
    """
    Adds group_name back to all_student_groups (SCIM PATCH add). Idempotent
    -- safe to call unconditionally for every group_NN, whether or not it
    was actually blocked, matching the classic backend's
    restore_cluster_permissions() style (unconditional restore of all
    groups, simple and robust).
    """
    logger = logger or logging.getLogger('SERVERLESS_ENFORCE')
    host = normalize_dbr_host(host)
    parent_id = find_group_id(host, token, ALL_STUDENT_GROUPS_NAME)
    member_id = find_group_id(host, token, group_name)
    if not parent_id or not member_id:
        logger.error(
            f"Cannot restore {group_name}: group id lookup failed "
            f"(parent={parent_id}, member={member_id})"
        )
        return False
    resp = requests.patch(
        f"{host}/api/2.0/preview/scim/v2/Groups/{parent_id}",
        headers=_scim_headers(token),
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "add", "path": "members", "value": [{"value": member_id}]}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    logger.info(f"Restored {group_name}: added back to {ALL_STUDENT_GROUPS_NAME}")
    return True
