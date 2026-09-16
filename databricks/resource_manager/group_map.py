"""
Resolves Databricks user_name (email) -> student group_name ('group_NN'),
for attributing Query History rows to a quota group (plan 2.3).

Reuses DataBricksGroups.list_groups() / get_group_members() rather than the
databricks-sdk package, or raw SCIM parsing. Two reasons:

1. This project's own top-level package is itself named `databricks`,
   which fully shadows the pip-installed `databricks-sdk` package's
   `databricks.sdk` namespace whenever this project's root is on sys.path
   -- which it always is here (pytest.ini's pythonpath=., the cron
   entrypoints). `from databricks.sdk import WorkspaceClient` is therefore
   unimportable from inside this codebase. Verified 2026-09-16 (pip show
   confirms the package is installed; `import databricks.sdk` still
   raises ModuleNotFoundError). serverless_usage.py and
   serverless_enforcement.py use `requests` directly for the same reason.
2. DataBricksGroups.get_group_members() already returns members as
   {'user_name': email} (it's what poll_clusters.py's get_emails_address()
   already relies on) -- reusing it avoids re-deriving that mapping from
   raw SCIM member entries, where 'display' is not guaranteed to be the
   email address.
"""
import re
import logging

# Matches the terraform-generated group names (dbr-serverless/main.tf:
# format("group_%02d", i + 1)).
GROUP_NAME_PATTERN = re.compile(r'^group_\d+$')


def build_email_to_group_map(groups_api, logger: logging.Logger = None) -> dict:
    """
    Returns {email: group_name} for every member of every workspace group
    matching GROUP_NAME_PATTERN. A user in no such group (staff, service
    principals) is simply absent from the map -- callers treat that as
    "ungrouped": reported, never blocked (plan 2.3).

    `groups_api` is a DataBricksGroups instance (duck-typed here so tests
    can pass a stub without importing the real databricks_cli-backed class).
    """
    logger = logger or logging.getLogger('SERVERLESS_GROUP_MAP')
    mapping = {}
    for group_name in groups_api.list_groups():
        if not GROUP_NAME_PATTERN.match(group_name):
            continue
        for member in groups_api.get_group_members(group_name):
            email = member.get('user_name')
            if not email:
                continue
            existing = mapping.get(email)
            if existing and existing != group_name:
                logger.warning(
                    f"{email} is a member of both {existing} and {group_name}; "
                    f"keeping {existing}."
                )
                continue
            mapping[email] = group_name
    return mapping
